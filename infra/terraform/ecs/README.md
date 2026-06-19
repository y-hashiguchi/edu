# ECS/Fargate Terraform

Creates the application runtime layer for an existing AWS network and ALB:

- ECS cluster with Container Insights
- backend, grading-worker, and frontend task definitions and services
- one-off Alembic migration task definition
- task/execution IAM roles
- separate frontend execution role without application-secret access
- S3 upload permissions restricted to `upload_prefix`
- Secrets Manager / SSM environment injection
- CloudWatch logs
- task security group accepting ports 8000/80 only from the ALB
- CPU target tracking autoscaling for backend and frontend
- CloudWatch alarms for sustained high CPU and insufficient running tasks
- DynamoDB deployment lock with TTL and point-in-time recovery

It does not create the VPC, subnets, NAT/VPC endpoints, ALB, RDS, ElastiCache,
S3 bucket, ECR repositories, ACM certificate, or DNS.

The AWS principal running `deploy_ecs.sh` needs ECS deployment permissions plus
`dynamodb:PutItem` and `dynamodb:DeleteItem` on the deployment lock table.

When using `../alb`, set its `target_type = "ip"` and pass the
`alb_security_group_id`, `api_target_group_arn`, and `web_target_group_arn`
outputs into this module.

## Usage

```bash
cp terraform.tfvars.example terraform.tfvars
# Replace every example ID, ARN, image tag, and secret ARN.
terraform init
terraform plan
terraform apply
```

Use immutable image tags or digests. `:latest` is rejected.
`UPLOAD_STORAGE_BACKEND` and S3 bucket/prefix/region environment variables are
derived by the module and cannot be overridden through `common_environment`.

Backend and frontend default to a 60% CPU target. The grading worker remains at
`worker_desired_count`; queue-depth autoscaling requires a custom Redis/CloudWatch
metric and is intentionally not approximated with CPU scaling.
Terraform ignores service `desired_count` drift after creation so a later apply
does not undo Application Auto Scaling decisions.

Set `alarm_action_arns` to SNS topic ARNs for operator notifications. Alarms are
created even when the list is empty, allowing notification wiring to be added
without recreating service resources.

Run the migration task definition output before deploying a release:

```bash
ECS_API_HEALTH_URL=https://api.example.com/healthz \
ECS_FRONTEND_HEALTH_URL=https://learn.example.com/login \
  ./infra/scripts/deploy_ecs.sh
```

The helper requires `aws`, `terraform`, and `jq`. It runs the migration task,
checks exit code `0`, then updates backend, worker, and frontend in order and
waits for each service to stabilize. When health URLs are set, it finishes with
retrying external HTTP checks through the ALB.
Before migration it requires all three services to be active, at desired
capacity, and have exactly one completed deployment. This rejects overlapping
deployments before they can race.
It also acquires a conditional DynamoDB lock with a one-hour stale-lock expiry,
so simultaneous deploy commands cannot both pass the preflight.
If a service update fails, already-updated services are restored to the task
definition revisions that were active before the deployment. The same rollback
runs when an optional external HTTP smoke check fails.

ECS service task-definition drift is intentionally ignored by Terraform. This
prevents `terraform apply` from deploying application tasks before the
migration gate. Terraform still registers each new task-definition revision;
the helper promotes those revisions after migration succeeds.

The AWS provider selection is committed in `.terraform.lock.hcl`. Update it
intentionally with `terraform init -upgrade` and validate both modules before
committing.
