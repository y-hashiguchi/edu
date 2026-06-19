mock_provider "aws" {}

run "fargate_target_groups_plan" {
  command = plan

  variables {
    project_name      = "edu"
    vpc_id            = "vpc-0123456789abcdef0"
    public_subnet_ids = ["subnet-0123456789abcdef0", "subnet-0fedcba9876543210"]
    certificate_arn   = "arn:aws:acm:ap-northeast-1:123456789012:certificate/01234567-89ab-cdef-0123-456789abcdef"
    app_domain        = "learn.example.com"
    api_domain        = "api.example.com"
    target_type       = "ip"
    instance_id       = null
  }

  assert {
    condition     = aws_lb_target_group.api.target_type == "ip"
    error_message = "API target group must use IP targets for Fargate."
  }

  assert {
    condition     = length(aws_lb_target_group_attachment.api) == 0
    error_message = "Fargate mode must not create EC2 target attachments."
  }

  assert {
    condition     = length(aws_security_group.app) == 0
    error_message = "Fargate mode must not create the EC2 app security group."
  }
}
