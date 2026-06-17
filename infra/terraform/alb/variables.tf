variable "aws_region" {
  type        = string
  description = "AWS region for ALB and target groups"
  default     = "ap-northeast-1"
}

variable "project_name" {
  type        = string
  description = "Prefix for resource names"
  default     = "edu"
}

variable "vpc_id" {
  type        = string
  description = "VPC where ALB and targets live"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets for the ALB (2+ AZs)"
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN (must cover app and api hostnames)"
}

variable "app_domain" {
  type        = string
  description = "Frontend hostname (e.g. learn.example.com)"
}

variable "api_domain" {
  type        = string
  description = "API hostname (e.g. api.example.com)"
}

variable "instance_id" {
  type        = string
  description = "EC2 instance ID running Docker Compose"
}

variable "api_port" {
  type        = number
  description = "Host port for FastAPI"
  default     = 8000
}

variable "web_port" {
  type        = number
  description = "Host port for frontend nginx"
  default     = 80
}
