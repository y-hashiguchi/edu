# ALB minimal Terraform (Sprint 28)

Reference module: HTTPS ALB with host-based routing to EC2 instance or
ECS/Fargate IP target groups.

**Not included:** VPC, EC2, RDS, ElastiCache, Route 53, ACM issuance.

## Usage

```bash
cp terraform.tfvars.example terraform.tfvars
# edit vpc_id, subnets, certificate_arn, instance_id, domains
terraform init
terraform plan
terraform apply
```

Point `learn.example.com` and `api.example.com` DNS at the output `alb_dns_name` (Route 53 ALIAS recommended).

## Requirements

- EC2 already running Docker Compose with backend:8000 and frontend:80 published to the host
- Security group on EC2 must allow inbound 8000/80 **only** from the ALB security group created here
- ACM certificate in the same region as the ALB, covering both hostnames

For ECS/Fargate, set `target_type = "ip"` and omit `instance_id`. Pass
`alb_security_group_id`, `api_target_group_arn`, and `web_target_group_arn`
outputs to `../ecs`. The EC2 app security group and target attachments are not
created in this mode.
