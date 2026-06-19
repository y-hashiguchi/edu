#!/usr/bin/env bash
set -euo pipefail

terraform_dir="${1:-infra/terraform/ecs}"

for command_name in aws jq terraform; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "required command not found: $command_name" >&2
    exit 1
  fi
done

tf_output() {
  terraform -chdir="$terraform_dir" output -raw "$1"
}

region="${AWS_REGION:-$(tf_output aws_region)}"
cluster_arn="$(tf_output cluster_arn)"
task_security_group_id="$(tf_output task_security_group_id)"
migration_task_definition_arn="$(tf_output migration_task_definition_arn)"
backend_service_name="$(tf_output backend_service_name)"
backend_task_definition_arn="$(tf_output backend_task_definition_arn)"
worker_service_name="$(tf_output worker_service_name)"
worker_task_definition_arn="$(tf_output worker_task_definition_arn)"
frontend_service_name="$(tf_output frontend_service_name)"
frontend_task_definition_arn="$(tf_output frontend_task_definition_arn)"
deployment_lock_table_name="$(tf_output deployment_lock_table_name)"

private_subnet_ids=()
while IFS= read -r subnet_id; do
  private_subnet_ids+=("$subnet_id")
done < <(
  terraform -chdir="$terraform_dir" output -json private_subnet_ids |
    jq -r '.[]'
)

if [[ "${#private_subnet_ids[@]}" -lt 2 ]]; then
  echo "expected at least two private subnet IDs" >&2
  exit 1
fi

subnets_csv="$(IFS=,; echo "${private_subnet_ids[*]}")"
network_configuration="awsvpcConfiguration={subnets=[$subnets_csv],securityGroups=[$task_security_group_id],assignPublicIp=DISABLED}"

lock_name="production"
lock_owner="${HOSTNAME:-unknown}:$$:$(date +%s)"
lock_acquired=0

release_deployment_lock() {
  if [[ "$lock_acquired" != "1" ]]; then
    return
  fi

  aws dynamodb delete-item \
    --region "$region" \
    --table-name "$deployment_lock_table_name" \
    --key "{\"lock_name\":{\"S\":\"$lock_name\"}}" \
    --condition-expression "lock_owner = :owner" \
    --expression-attribute-values "{\":owner\":{\"S\":\"$lock_owner\"}}" \
    >/dev/null 2>&1 || true
}

trap release_deployment_lock EXIT

now_epoch="$(date +%s)"
expires_epoch="$((now_epoch + 3600))"
lock_item="$(
  jq -cn \
    --arg lock_name "$lock_name" \
    --arg lock_owner "$lock_owner" \
    --arg expires_at "$expires_epoch" \
    '{
      lock_name: {S: $lock_name},
      lock_owner: {S: $lock_owner},
      expires_at: {N: $expires_at}
    }'
)"

if ! aws dynamodb put-item \
  --region "$region" \
  --table-name "$deployment_lock_table_name" \
  --item "$lock_item" \
  --condition-expression "attribute_not_exists(lock_name) OR expires_at < :now" \
  --expression-attribute-values "{\":now\":{\"N\":\"$now_epoch\"}}" \
  >/dev/null; then
  echo "another ECS deployment holds the lock: $deployment_lock_table_name/$lock_name" >&2
  exit 1
fi
lock_acquired=1

assert_service_stable() {
  local service_name="$1"
  local service_status

  service_status="$(
    aws ecs describe-services \
      --region "$region" \
      --cluster "$cluster_arn" \
      --services "$service_name" \
      --query 'services[0].[status,runningCount,desiredCount,length(deployments),deployments[0].rolloutState]' \
      --output text
  )"

  read -r status running_count desired_count deployment_count rollout_state <<<"$service_status"
  if [[ "$status" != "ACTIVE" ||
    "$running_count" != "$desired_count" ||
    "$deployment_count" != "1" ||
    "$rollout_state" != "COMPLETED" ]]; then
    echo "service is not stable before deploy: $service_name ($service_status)" >&2
    return 1
  fi
}

echo "Checking ECS services are stable before migration..."
assert_service_stable "$backend_service_name"
assert_service_stable "$worker_service_name"
assert_service_stable "$frontend_service_name"

echo "Running database migration task..."
migration_task_arn="$(
  aws ecs run-task \
    --region "$region" \
    --cluster "$cluster_arn" \
    --launch-type FARGATE \
    --task-definition "$migration_task_definition_arn" \
    --network-configuration "$network_configuration" \
    --query 'tasks[0].taskArn' \
    --output text
)"

if [[ -z "$migration_task_arn" || "$migration_task_arn" == "None" ]]; then
  echo "migration task was not started" >&2
  exit 1
fi

aws ecs wait tasks-stopped \
  --region "$region" \
  --cluster "$cluster_arn" \
  --tasks "$migration_task_arn"

migration_exit_code="$(
  aws ecs describe-tasks \
    --region "$region" \
    --cluster "$cluster_arn" \
    --tasks "$migration_task_arn" \
    --query 'tasks[0].containers[0].exitCode' \
    --output text
)"

if [[ "$migration_exit_code" != "0" ]]; then
  stop_reason="$(
    aws ecs describe-tasks \
      --region "$region" \
      --cluster "$cluster_arn" \
      --tasks "$migration_task_arn" \
      --query 'tasks[0].stoppedReason' \
      --output text
  )"
  echo "migration failed: exit=$migration_exit_code reason=$stop_reason" >&2
  exit 1
fi

update_service() {
  local service_name="$1"
  local task_definition_arn="$2"

  echo "Updating ECS service: $service_name"
  aws ecs update-service \
    --region "$region" \
    --cluster "$cluster_arn" \
    --service "$service_name" \
    --task-definition "$task_definition_arn" \
    --force-new-deployment \
    >/dev/null || return 1

  aws ecs wait services-stable \
    --region "$region" \
    --cluster "$cluster_arn" \
    --services "$service_name" || return 1
}

current_task_definition() {
  local service_name="$1"

  aws ecs describe-services \
    --region "$region" \
    --cluster "$cluster_arn" \
    --services "$service_name" \
    --query 'services[0].taskDefinition' \
    --output text
}

updated_services=()
previous_task_definitions=()

rollback_updated_services() {
  local index

  echo "Rolling back updated ECS services..." >&2
  for ((index = ${#updated_services[@]} - 1; index >= 0; index--)); do
    aws ecs update-service \
      --region "$region" \
      --cluster "$cluster_arn" \
      --service "${updated_services[$index]}" \
      --task-definition "${previous_task_definitions[$index]}" \
      --force-new-deployment \
      >/dev/null || true
    aws ecs wait services-stable \
      --region "$region" \
      --cluster "$cluster_arn" \
      --services "${updated_services[$index]}" || true
  done
}

deploy_service() {
  local service_name="$1"
  local task_definition_arn="$2"
  local previous_task_definition

  previous_task_definition="$(current_task_definition "$service_name")"
  if [[ -z "$previous_task_definition" || "$previous_task_definition" == "None" ]]; then
    echo "could not resolve current task definition for service: $service_name" >&2
    return 1
  fi

  updated_services+=("$service_name")
  previous_task_definitions+=("$previous_task_definition")
  update_service "$service_name" "$task_definition_arn"
}

if ! deploy_service "$backend_service_name" "$backend_task_definition_arn"; then
  rollback_updated_services
  exit 1
fi
if ! deploy_service "$worker_service_name" "$worker_task_definition_arn"; then
  rollback_updated_services
  exit 1
fi
if ! deploy_service "$frontend_service_name" "$frontend_task_definition_arn"; then
  rollback_updated_services
  exit 1
fi

run_http_smoke_checks() {
  if [[ -n "${ECS_API_HEALTH_URL:-}" || -n "${ECS_FRONTEND_HEALTH_URL:-}" ]]; then
    if ! command -v curl >/dev/null 2>&1; then
      echo "required command not found for HTTP smoke checks: curl" >&2
      return 1
    fi
  fi

  if [[ -n "${ECS_API_HEALTH_URL:-}" ]]; then
    echo "Checking API health: $ECS_API_HEALTH_URL"
    curl --fail --silent --show-error --retry 5 --retry-all-errors "$ECS_API_HEALTH_URL" >/dev/null ||
      return 1
  fi

  if [[ -n "${ECS_FRONTEND_HEALTH_URL:-}" ]]; then
    echo "Checking frontend health: $ECS_FRONTEND_HEALTH_URL"
    curl --fail --silent --show-error --retry 5 --retry-all-errors "$ECS_FRONTEND_HEALTH_URL" >/dev/null ||
      return 1
  fi
}

if ! run_http_smoke_checks; then
  rollback_updated_services
  exit 1
fi

echo "ECS deployment completed."
