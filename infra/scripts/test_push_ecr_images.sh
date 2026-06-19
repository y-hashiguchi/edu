#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

cat >"$temp_dir/git" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == "status --porcelain --untracked-files=all -- backend frontend" ]]; then
  [[ "${MOCK_GIT_DIRTY:-0}" == "1" ]] && echo " M backend/app/main.py"
elif [[ "$*" == "rev-parse --short=12 HEAD" ]]; then
  echo "abc1234def56"
fi
EOF

cat >"$temp_dir/terraform" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
key="${@: -1}"
case "$key" in
  backend_repository_url) echo "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/edu-backend" ;;
  frontend_repository_url) echo "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/edu-frontend" ;;
  aws_region) echo "ap-northeast-1" ;;
  *) exit 1 ;;
esac
EOF

cat >"$temp_dir/aws" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$MOCK_AWS_LOG"
if [[ "$*" == "ecr get-login-password --region ap-northeast-1" ]]; then
  echo "mock-password"
fi
EOF

cat >"$temp_dir/docker" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "login" ]]; then
  cat >/dev/null
fi
printf '%s\n' "$*" >>"$MOCK_DOCKER_LOG"
EOF

chmod +x "$temp_dir/aws" "$temp_dir/docker" "$temp_dir/git" "$temp_dir/terraform"

export MOCK_AWS_LOG="$temp_dir/aws.log"
export MOCK_DOCKER_LOG="$temp_dir/docker.log"
export PATH="$temp_dir:$PATH"

output="$(
  VITE_API_BASE_URL=https://api.example.com \
    "$repo_root/infra/scripts/push_ecr_images.sh" mock-terraform
)"

grep -q "ecr get-login-password --region ap-northeast-1" "$MOCK_AWS_LOG"
grep -q "login --username AWS --password-stdin 123456789012.dkr.ecr.ap-northeast-1.amazonaws.com" "$MOCK_DOCKER_LOG"
grep -q "build --pull -t .*edu-backend:sha-abc1234def56 ./backend" "$MOCK_DOCKER_LOG"
grep -q "build --pull -f frontend/Dockerfile.prod --build-arg VITE_API_BASE_URL=https://api.example.com -t .*edu-frontend:sha-abc1234def56 ./frontend" "$MOCK_DOCKER_LOG"
grep -q "push .*edu-backend:sha-abc1234def56" "$MOCK_DOCKER_LOG"
grep -q "push .*edu-frontend:sha-abc1234def56" "$MOCK_DOCKER_LOG"
grep -q "backend_image=.*edu-backend:sha-abc1234def56" <<<"$output"
grep -q "frontend_image=.*edu-frontend:sha-abc1234def56" <<<"$output"

if MOCK_GIT_DIRTY=1 VITE_API_BASE_URL=https://api.example.com \
  "$repo_root/infra/scripts/push_ecr_images.sh" mock-terraform >/dev/null 2>&1; then
  echo "expected dirty worktree rejection" >&2
  exit 1
fi

echo "push_ecr_images helper tests passed"
