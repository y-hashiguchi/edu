#!/usr/bin/env bash
set -euo pipefail

ecr_terraform_dir="${1:-infra/terraform/ecr}"
api_base_url="${VITE_API_BASE_URL:-}"

for command_name in aws docker git terraform; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "required command not found: $command_name" >&2
    exit 1
  fi
done

if [[ -z "$api_base_url" ]]; then
  echo "VITE_API_BASE_URL is required" >&2
  exit 1
fi

if [[ "${ALLOW_DIRTY_BUILD:-0}" != "1" &&
  -n "$(git status --porcelain --untracked-files=all -- backend frontend)" ]]; then
  echo "refusing to publish images from dirty backend/frontend build contexts" >&2
  exit 1
fi

commit_sha="$(git rev-parse --short=12 HEAD)"
image_tag="sha-$commit_sha"
backend_repository_url="$(terraform -chdir="$ecr_terraform_dir" output -raw backend_repository_url)"
frontend_repository_url="$(terraform -chdir="$ecr_terraform_dir" output -raw frontend_repository_url)"
registry="${backend_repository_url%%/*}"

if [[ "${frontend_repository_url%%/*}" != "$registry" ]]; then
  echo "backend and frontend repositories must use the same ECR registry" >&2
  exit 1
fi

region="${AWS_REGION:-$(terraform -chdir="$ecr_terraform_dir" output -raw aws_region 2>/dev/null || true)}"
if [[ -z "$region" ]]; then
  region="$(aws configure get region)"
fi
if [[ -z "$region" ]]; then
  echo "AWS region is required through AWS_REGION, Terraform output, or AWS config" >&2
  exit 1
fi

aws ecr get-login-password --region "$region" |
  docker login --username AWS --password-stdin "$registry"

backend_image="$backend_repository_url:$image_tag"
frontend_image="$frontend_repository_url:$image_tag"

docker build --pull -t "$backend_image" ./backend
docker build --pull \
  -f frontend/Dockerfile.prod \
  --build-arg "VITE_API_BASE_URL=$api_base_url" \
  -t "$frontend_image" \
  ./frontend

docker push "$backend_image"
docker push "$frontend_image"

printf 'backend_image=%s\nfrontend_image=%s\n' "$backend_image" "$frontend_image"
