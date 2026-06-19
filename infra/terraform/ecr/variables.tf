variable "aws_region" {
  type        = string
  description = "AWS region for ECR repositories"
  default     = "ap-northeast-1"
}

variable "project_name" {
  type        = string
  description = "Prefix for repository names"
  default     = "edu"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,27}$", var.project_name))
    error_message = "project_name must be 2-28 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "tagged_image_retention_count" {
  type        = number
  description = "Number of tagged release images retained per repository"
  default     = 30

  validation {
    condition     = var.tagged_image_retention_count >= 5
    error_message = "tagged_image_retention_count must be at least 5."
  }
}

variable "untagged_image_retention_days" {
  type        = number
  description = "Days before untagged images expire"
  default     = 7

  validation {
    condition     = var.untagged_image_retention_days >= 1
    error_message = "untagged_image_retention_days must be at least 1."
  }
}

variable "kms_key_arn" {
  type        = string
  description = "Optional customer-managed KMS key ARN for ECR encryption"
  default     = null
  nullable    = true

  validation {
    condition     = var.kms_key_arn == null || can(regex("^arn:aws[a-zA-Z-]*:kms:", var.kms_key_arn))
    error_message = "kms_key_arn must be a KMS key ARN when set."
  }
}

variable "tags" {
  type        = map(string)
  description = "Additional resource tags"
  default     = {}
}
