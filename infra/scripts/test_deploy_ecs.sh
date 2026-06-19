#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

cat >"$temp_dir/terraform" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

key="${@: -1}"
if [[ "$*" == *" output -json private_subnet_ids" ]]; then
  printf '%s\n' '["subnet-a","subnet-b"]'
  exit 0
fi

case "$key" in
  aws_region) echo "ap-northeast-1" ;;
  cluster_arn) echo "arn:aws:ecs:ap-northeast-1:123456789012:cluster/edu-prod" ;;
  task_security_group_id) echo "sg-0123456789abcdef0" ;;
  migration_task_definition_arn) echo "arn:aws:ecs:ap-northeast-1:123456789012:task-definition/edu-backend-migrate:2" ;;
  backend_service_name) echo "backend" ;;
  backend_task_definition_arn) echo "arn:aws:ecs:ap-northeast-1:123456789012:task-definition/edu-backend:2" ;;
  worker_service_name) echo "grading-worker" ;;
  worker_task_definition_arn) echo "arn:aws:ecs:ap-northeast-1:123456789012:task-definition/edu-grading-worker:2" ;;
  frontend_service_name) echo "frontend" ;;
  frontend_task_definition_arn) echo "arn:aws:ecs:ap-northeast-1:123456789012:task-definition/edu-frontend:2" ;;
  deployment_lock_table_name) echo "edu-ecs-deployment-lock" ;;
  *) echo "unexpected terraform output: $key" >&2; exit 1 ;;
esac
EOF

cat >"$temp_dir/jq" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cat >/dev/null
printf '%s\n' "subnet-a" "subnet-b"
EOF

cat >"$temp_dir/aws" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$MOCK_AWS_LOG"

if [[ "$*" == *" run-task "* ]]; then
  echo "arn:aws:ecs:ap-northeast-1:123456789012:task/edu-prod/migration"
elif [[ "$*" == "dynamodb put-item "* && "${MOCK_LOCK_HELD:-0}" == "1" ]]; then
  exit 1
elif [[ "$*" == *" describe-tasks "*"containers[0].exitCode"* ]]; then
  echo "${MOCK_MIGRATION_EXIT:-0}"
elif [[ "$*" == *" describe-tasks "*"stoppedReason"* ]]; then
  echo "mock migration failure"
elif [[ "$*" == *" describe-services "* ]]; then
  if [[ "$*" == *"length(deployments)"* ]]; then
    if [[ "$*" == *"--services ${MOCK_UNSTABLE_SERVICE:-__never__}"* ]]; then
      echo "ACTIVE 1 2 2 IN_PROGRESS"
    else
      echo "ACTIVE 2 2 1 COMPLETED"
    fi
  elif [[ "$*" == *"--services backend"* ]]; then
    echo "arn:aws:ecs:ap-northeast-1:123456789012:task-definition/edu-backend:1"
  elif [[ "$*" == *"--services grading-worker"* ]]; then
    echo "arn:aws:ecs:ap-northeast-1:123456789012:task-definition/edu-grading-worker:1"
  elif [[ "$*" == *"--services frontend"* ]]; then
    echo "arn:aws:ecs:ap-northeast-1:123456789012:task-definition/edu-frontend:1"
  fi
elif [[ "$*" == *" update-service "*"--service ${MOCK_FAIL_SERVICE:-__never__} "* &&
  "$*" != *":1 "* ]]; then
  exit 1
fi
EOF

cat >"$temp_dir/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$MOCK_CURL_LOG"
if [[ "${MOCK_CURL_FAIL:-0}" == "1" ]]; then
  exit 1
fi
EOF

chmod +x "$temp_dir/aws" "$temp_dir/curl" "$temp_dir/jq" "$temp_dir/terraform"

export MOCK_AWS_LOG="$temp_dir/aws.log"
export MOCK_CURL_LOG="$temp_dir/curl.log"
export PATH="$temp_dir:$PATH"

ECS_API_HEALTH_URL="https://api.example.com/healthz" \
ECS_FRONTEND_HEALTH_URL="https://learn.example.com/login" \
MOCK_MIGRATION_EXIT=0 \
  "$repo_root/infra/scripts/deploy_ecs.sh" mock-terraform >/dev/null

update_lines="$(grep " update-service " "$MOCK_AWS_LOG")"
[[ "$(printf '%s\n' "$update_lines" | wc -l | tr -d ' ')" == "3" ]]
printf '%s\n' "$update_lines" | sed -n '1p' | grep -q -- "--service backend "
printf '%s\n' "$update_lines" | sed -n '2p' | grep -q -- "--service grading-worker "
printf '%s\n' "$update_lines" | sed -n '3p' | grep -q -- "--service frontend "
grep -q "https://api.example.com/healthz" "$MOCK_CURL_LOG"
grep -q "https://learn.example.com/login" "$MOCK_CURL_LOG"
grep -q "^dynamodb delete-item " "$MOCK_AWS_LOG"

: >"$MOCK_AWS_LOG"
if MOCK_MIGRATION_EXIT=1 "$repo_root/infra/scripts/deploy_ecs.sh" mock-terraform >/dev/null 2>&1; then
  echo "expected migration failure to stop deployment" >&2
  exit 1
fi

if grep -q " update-service " "$MOCK_AWS_LOG"; then
  echo "services were updated after migration failure" >&2
  exit 1
fi
grep -q "^dynamodb delete-item " "$MOCK_AWS_LOG"

: >"$MOCK_AWS_LOG"
if MOCK_UNSTABLE_SERVICE=backend \
  "$repo_root/infra/scripts/deploy_ecs.sh" mock-terraform >/dev/null 2>&1; then
  echo "expected unstable service preflight failure" >&2
  exit 1
fi

if grep -q " run-task " "$MOCK_AWS_LOG"; then
  echo "migration started while a service was unstable" >&2
  exit 1
fi

: >"$MOCK_AWS_LOG"
if MOCK_LOCK_HELD=1 \
  "$repo_root/infra/scripts/deploy_ecs.sh" mock-terraform >/dev/null 2>&1; then
  echo "expected deployment lock acquisition failure" >&2
  exit 1
fi

if grep -q " run-task " "$MOCK_AWS_LOG"; then
  echo "migration started without the deployment lock" >&2
  exit 1
fi
if grep -q "^dynamodb delete-item " "$MOCK_AWS_LOG"; then
  echo "unowned deployment lock was deleted" >&2
  exit 1
fi

: >"$MOCK_AWS_LOG"
if MOCK_FAIL_SERVICE=grading-worker \
  "$repo_root/infra/scripts/deploy_ecs.sh" mock-terraform >/dev/null 2>&1; then
  echo "expected service update failure" >&2
  exit 1
fi

grep -q -- "--service backend --task-definition .*edu-backend:2" "$MOCK_AWS_LOG"
grep -q -- "--service grading-worker --task-definition .*edu-grading-worker:2" "$MOCK_AWS_LOG"
grep -q -- "--service grading-worker --task-definition .*edu-grading-worker:1" "$MOCK_AWS_LOG"
grep -q -- "--service backend --task-definition .*edu-backend:1" "$MOCK_AWS_LOG"
if grep -q -- "--service frontend --task-definition .*edu-frontend:2" "$MOCK_AWS_LOG"; then
  echo "frontend was updated after worker failure" >&2
  exit 1
fi

: >"$MOCK_AWS_LOG"
: >"$MOCK_CURL_LOG"
if ECS_API_HEALTH_URL="https://api.example.com/healthz" \
  MOCK_CURL_FAIL=1 \
  "$repo_root/infra/scripts/deploy_ecs.sh" mock-terraform >/dev/null 2>&1; then
  echo "expected HTTP smoke failure" >&2
  exit 1
fi

grep -q -- "--service frontend --task-definition .*edu-frontend:1" "$MOCK_AWS_LOG"
grep -q -- "--service grading-worker --task-definition .*edu-grading-worker:1" "$MOCK_AWS_LOG"
grep -q -- "--service backend --task-definition .*edu-backend:1" "$MOCK_AWS_LOG"

echo "deploy_ecs helper tests passed"
