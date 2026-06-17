variable "aws_region" {
  type        = string
  description = "AWS region for ALB and target groups"
  default     = "ap-northeast-1"

  validation {
    condition     = length(trimspace(var.aws_region)) > 0
    error_message = "aws_region must not be empty."
  }
}

variable "project_name" {
  type        = string
  description = "Prefix for resource names"
  default     = "edu"

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]{1,27}$", var.project_name))
    error_message = "project_name must be 2-28 characters, start with a letter, and contain only letters, numbers, and hyphens."
  }
}

variable "vpc_id" {
  type        = string
  description = "VPC where ALB and targets live"

  validation {
    condition     = can(regex("^vpc-[0-9a-f]+$", var.vpc_id))
    error_message = "vpc_id must look like vpc-xxxxxxxx."
  }
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets for the ALB (2+ AZs)"

  validation {
    condition     = length(var.public_subnet_ids) >= 2
    error_message = "public_subnet_ids must include at least two public subnets in different AZs."
  }
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN (must cover app and api hostnames)"

  validation {
    condition     = can(regex("^arn:aws[a-zA-Z-]*:acm:", var.certificate_arn))
    error_message = "certificate_arn must be an ACM certificate ARN."
  }
}

variable "app_domain" {
  type        = string
  description = "Frontend hostname (e.g. learn.example.com)"

  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", var.app_domain))
    error_message = "app_domain must be a DNS hostname."
  }
}

variable "api_domain" {
  type        = string
  description = "API hostname (e.g. api.example.com)"

  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", var.api_domain))
    error_message = "api_domain must be a DNS hostname."
  }
}

variable "instance_id" {
  type        = string
  description = "EC2 instance ID running Docker Compose"

  validation {
    condition     = can(regex("^i-[0-9a-f]+$", var.instance_id))
    error_message = "instance_id must look like i-xxxxxxxx."
  }
}

variable "api_port" {
  type        = number
  description = "Host port for FastAPI"
  default     = 8000

  validation {
    condition     = var.api_port > 0 && var.api_port <= 65535
    error_message = "api_port must be between 1 and 65535."
  }
}

variable "web_port" {
  type        = number
  description = "Host port for frontend nginx"
  default     = 80

  validation {
    condition     = var.web_port > 0 && var.web_port <= 65535
    error_message = "web_port must be between 1 and 65535."
  }
}
