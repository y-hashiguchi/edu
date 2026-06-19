# ECR Terraform

Creates immutable backend and frontend repositories:

- `edu-backend`
- `edu-frontend`
- tag immutability
- scan on push
- AES-256 encryption by default, optional customer-managed KMS key
- untagged image expiration
- retention of recent `sha-*` release tags

## Usage

```bash
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

Tag release images with the git SHA:

```bash
VITE_API_BASE_URL=https://api.example.com \
  ./infra/scripts/push_ecr_images.sh
```

The helper rejects changes inside the backend/frontend Docker build contexts,
logs in to the output ECR registry, builds both production images, pushes
`sha-<12-char-commit>` tags, and prints the image URIs to set as ECS
`backend_image` and `frontend_image`. Unrelated docs or handoff files do not
block image publication.
