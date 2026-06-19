variable "aws_region" {
  type        = string
  description = "AWS region for ECS and CloudWatch resources"
  default     = "ap-northeast-1"
}

variable "project_name" {
  type        = string
  description = "Prefix for resource names"
  default     = "edu"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,27}$", var.project_name))
    error_message = "project_name must be 2-28 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "vpc_id" {
  type        = string
  description = "VPC containing the ECS tasks and ALB"

  validation {
    condition     = can(regex("^vpc-[0-9a-f]+$", var.vpc_id))
    error_message = "vpc_id must look like vpc-xxxxxxxx."
  }
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for Fargate tasks"

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "private_subnet_ids must contain at least two subnets."
  }
}

variable "alb_security_group_id" {
  type        = string
  description = "Security group attached to the ALB"
}

variable "api_target_group_arn" {
  type        = string
  description = "ALB target group ARN for backend port 8000"
}

variable "web_target_group_arn" {
  type        = string
  description = "ALB target group ARN for frontend port 80"
}

variable "backend_image" {
  type        = string
  description = "Immutable backend ECR image URI, including tag or digest"

  validation {
    condition     = length(trimspace(var.backend_image)) > 0 && !endswith(var.backend_image, ":latest")
    error_message = "backend_image must be non-empty and must not use the latest tag."
  }
}

variable "frontend_image" {
  type        = string
  description = "Immutable frontend ECR image URI, including tag or digest"

  validation {
    condition     = length(trimspace(var.frontend_image)) > 0 && !endswith(var.frontend_image, ":latest")
    error_message = "frontend_image must be non-empty and must not use the latest tag."
  }
}

variable "upload_bucket_arn" {
  type        = string
  description = "ARN of the S3 bucket used for submission uploads"

  validation {
    condition     = can(regex("^arn:aws[a-zA-Z-]*:s3:::", var.upload_bucket_arn))
    error_message = "upload_bucket_arn must be an S3 bucket ARN."
  }
}

variable "upload_prefix" {
  type        = string
  description = "S3 key prefix reserved for submission uploads"
  default     = "uploads"

  validation {
    condition     = can(regex("^[A-Za-z0-9!_.*'()/-]+$", var.upload_prefix)) && trim(var.upload_prefix, "/") != ""
    error_message = "upload_prefix must be a non-empty S3 key prefix without a leading-only slash."
  }
}

variable "common_environment" {
  type        = map(string)
  description = "Non-secret environment variables shared by backend and worker"

  validation {
    condition = alltrue([
      for key in keys(var.common_environment) :
      !contains([
        "ANTHROPIC_API_KEY",
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "REDIS_URL",
        "S3_UPLOAD_BUCKET",
        "S3_UPLOAD_PREFIX",
        "S3_UPLOAD_REGION",
        "UPLOAD_STORAGE_BACKEND",
      ], key)
    ])
    error_message = "Secrets and module-managed S3 settings must not be supplied through common_environment."
  }
}

variable "secret_arns" {
  type        = map(string)
  description = "Environment variable name to Secrets Manager secret or SSM parameter ARN"

  validation {
    condition = alltrue([
      for key in ["ANTHROPIC_API_KEY", "DATABASE_URL", "JWT_SECRET_KEY", "REDIS_URL"] :
      contains(keys(var.secret_arns), key)
    ])
    error_message = "secret_arns must include ANTHROPIC_API_KEY, DATABASE_URL, JWT_SECRET_KEY, and REDIS_URL."
  }
}

variable "kms_key_arns" {
  type        = list(string)
  description = "Optional customer-managed KMS keys used by injected secrets"
  default     = []
}

variable "backend_desired_count" {
  type        = number
  description = "Desired backend task count"
  default     = 2

  validation {
    condition     = var.backend_desired_count >= 1
    error_message = "backend_desired_count must be at least 1."
  }

  validation {
    condition = (
      var.backend_desired_count >= var.backend_min_count &&
      var.backend_desired_count <= var.backend_max_count
    )
    error_message = "backend_desired_count must be within the backend autoscaling range."
  }
}

variable "backend_min_count" {
  type        = number
  description = "Minimum backend task count for autoscaling"
  default     = 2

  validation {
    condition     = var.backend_min_count >= 1
    error_message = "backend_min_count must be at least 1."
  }
}

variable "backend_max_count" {
  type        = number
  description = "Maximum backend task count for autoscaling"
  default     = 6

  validation {
    condition     = var.backend_max_count >= var.backend_min_count
    error_message = "backend_max_count must be greater than or equal to backend_min_count."
  }
}

variable "worker_desired_count" {
  type        = number
  description = "Desired grading worker task count"
  default     = 1

  validation {
    condition     = var.worker_desired_count >= 1
    error_message = "worker_desired_count must be at least 1."
  }
}

variable "frontend_desired_count" {
  type        = number
  description = "Desired frontend task count"
  default     = 2

  validation {
    condition     = var.frontend_desired_count >= 1
    error_message = "frontend_desired_count must be at least 1."
  }

  validation {
    condition = (
      var.frontend_desired_count >= var.frontend_min_count &&
      var.frontend_desired_count <= var.frontend_max_count
    )
    error_message = "frontend_desired_count must be within the frontend autoscaling range."
  }
}

variable "frontend_min_count" {
  type        = number
  description = "Minimum frontend task count for autoscaling"
  default     = 2

  validation {
    condition     = var.frontend_min_count >= 1
    error_message = "frontend_min_count must be at least 1."
  }
}

variable "frontend_max_count" {
  type        = number
  description = "Maximum frontend task count for autoscaling"
  default     = 4

  validation {
    condition     = var.frontend_max_count >= var.frontend_min_count
    error_message = "frontend_max_count must be greater than or equal to frontend_min_count."
  }
}

variable "autoscaling_cpu_target" {
  type        = number
  description = "Target average CPU utilization for backend and frontend services"
  default     = 60

  validation {
    condition     = var.autoscaling_cpu_target >= 10 && var.autoscaling_cpu_target <= 90
    error_message = "autoscaling_cpu_target must be between 10 and 90."
  }
}

variable "autoscaling_scale_in_cooldown" {
  type        = number
  description = "Seconds to wait before another scale-in action"
  default     = 300
}

variable "autoscaling_scale_out_cooldown" {
  type        = number
  description = "Seconds to wait before another scale-out action"
  default     = 60
}

variable "cpu_alarm_threshold" {
  type        = number
  description = "Average CPU percentage that triggers a sustained high-CPU alarm"
  default     = 85

  validation {
    condition     = var.cpu_alarm_threshold > var.autoscaling_cpu_target && var.cpu_alarm_threshold <= 100
    error_message = "cpu_alarm_threshold must be above autoscaling_cpu_target and at most 100."
  }
}

variable "alarm_action_arns" {
  type        = list(string)
  description = "Optional SNS topic ARNs notified by CloudWatch alarms"
  default     = []

  validation {
    condition = alltrue([
      for arn in var.alarm_action_arns :
      can(regex("^arn:aws[a-zA-Z-]*:sns:", arn))
    ])
    error_message = "alarm_action_arns must contain SNS topic ARNs."
  }
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention"
  default     = 30
}

variable "enable_execute_command" {
  type        = bool
  description = "Enable ECS Exec for operational debugging"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Additional resource tags"
  default     = {}
}
