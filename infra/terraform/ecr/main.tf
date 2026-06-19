locals {
  repositories = toset(["backend", "frontend"])
  tags = merge(
    {
      Project   = var.project_name
      ManagedBy = "Terraform"
    },
    var.tags,
  )
}

resource "aws_ecr_repository" "app" {
  for_each = local.repositories

  name                 = "${var.project_name}-${each.key}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = var.kms_key_arn == null ? "AES256" : "KMS"
    kms_key         = var.kms_key_arn
  }

  tags = local.tags
}

resource "aws_ecr_lifecycle_policy" "app" {
  for_each = aws_ecr_repository.app

  repository = each.value.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = var.untagged_image_retention_days
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Retain recent tagged releases"
        selection = {
          tagStatus = "tagged"
          tagPrefixList = [
            "sha-",
          ]
          countType   = "imageCountMoreThan"
          countNumber = var.tagged_image_retention_count
        }
        action = {
          type = "expire"
        }
      },
    ]
  })
}
