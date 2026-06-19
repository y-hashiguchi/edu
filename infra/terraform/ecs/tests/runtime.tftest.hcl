mock_provider "aws" {}

run "ecs_runtime_plan" {
  command = plan

  variables {
    project_name          = "edu"
    vpc_id                = "vpc-0123456789abcdef0"
    private_subnet_ids    = ["subnet-0123456789abcdef0", "subnet-0fedcba9876543210"]
    alb_security_group_id = "sg-0123456789abcdef0"
    api_target_group_arn  = "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:targetgroup/edu-api/0123456789abcdef"
    web_target_group_arn  = "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:targetgroup/edu-web/0123456789abcdef"
    backend_image         = "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/edu-backend:abc1234"
    frontend_image        = "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/edu-frontend:abc1234"
    upload_bucket_arn     = "arn:aws:s3:::edu-production-uploads"

    common_environment = {
      CORS_ALLOW_ORIGINS              = "https://learn.example.com"
      GRADING_ASYNC_ENABLED           = "true"
      CURRICULUM_CACHE_PUBSUB_ENABLED = "true"
      CLAUDE_STUB_MODE                = "false"
      EMBEDDING_STUB_MODE             = "false"
    }

    secret_arns = {
      ANTHROPIC_API_KEY = "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:edu/anthropic-abc123"
      DATABASE_URL      = "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:edu/database-url-abc123"
      JWT_SECRET_KEY    = "arn:aws:ssm:ap-northeast-1:123456789012:parameter/edu/jwt-secret"
      REDIS_URL         = "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:edu/redis-url-abc123"
    }
  }

  assert {
    condition     = aws_ecs_service.backend.launch_type == "FARGATE"
    error_message = "Backend service must use Fargate."
  }

  assert {
    condition     = aws_ecs_service.backend.deployment_circuit_breaker[0].rollback
    error_message = "Backend deployment circuit breaker must roll back failures."
  }

  assert {
    condition     = aws_ecs_task_definition.migration.family == "edu-backend-migrate"
    error_message = "Migration task definition must be available for one-off deploy steps."
  }

  assert {
    condition = one([
      for item in jsondecode(aws_ecs_task_definition.backend.container_definitions)[0].environment :
      item.value if item.name == "UPLOAD_STORAGE_BACKEND"
    ]) == "s3"
    error_message = "The module must force the S3 upload backend."
  }

  assert {
    condition = length([
      for item in jsondecode(aws_ecs_task_definition.backend.container_definitions)[0].environment :
      item if item.name == "DATABASE_URL"
    ]) == 0
    error_message = "Secret values must not appear in the plaintext environment list."
  }

  assert {
    condition = length([
      for item in jsondecode(aws_ecs_task_definition.backend.container_definitions)[0].secrets :
      item if item.name == "DATABASE_URL"
    ]) == 1
    error_message = "DATABASE_URL must be injected through the ECS secrets list."
  }

  assert {
    condition     = !contains(keys(jsondecode(aws_ecs_task_definition.frontend.container_definitions)[0]), "secrets")
    error_message = "Frontend container definition must not inject backend application secrets."
  }

  assert {
    condition     = aws_appautoscaling_target.backend.min_capacity == 2 && aws_appautoscaling_target.backend.max_capacity == 6
    error_message = "Backend autoscaling must use the production baseline range."
  }

  assert {
    condition     = aws_appautoscaling_policy.backend_cpu.target_tracking_scaling_policy_configuration[0].target_value == 60
    error_message = "Backend autoscaling must target 60 percent average CPU by default."
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.high_cpu) == 3
    error_message = "All ECS services must have sustained high-CPU alarms."
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.running_tasks_low) == 3
    error_message = "All ECS services must have running-task-count alarms."
  }

  assert {
    condition     = aws_dynamodb_table.deployment_lock.billing_mode == "PAY_PER_REQUEST"
    error_message = "Deployment locking must not require provisioned DynamoDB capacity."
  }
}

run "reject_latest_images" {
  command = plan

  variables {
    project_name          = "edu"
    vpc_id                = "vpc-0123456789abcdef0"
    private_subnet_ids    = ["subnet-0123456789abcdef0", "subnet-0fedcba9876543210"]
    alb_security_group_id = "sg-0123456789abcdef0"
    api_target_group_arn  = "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:targetgroup/edu-api/0123456789abcdef"
    web_target_group_arn  = "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:targetgroup/edu-web/0123456789abcdef"
    backend_image         = "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/edu-backend:latest"
    frontend_image        = "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/edu-frontend:latest"
    upload_bucket_arn     = "arn:aws:s3:::edu-production-uploads"
    common_environment    = {}
    secret_arns = {
      ANTHROPIC_API_KEY = "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:edu/anthropic-abc123"
      DATABASE_URL      = "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:edu/database-url-abc123"
      JWT_SECRET_KEY    = "arn:aws:ssm:ap-northeast-1:123456789012:parameter/edu/jwt-secret"
      REDIS_URL         = "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:edu/redis-url-abc123"
    }
  }

  expect_failures = [
    var.backend_image,
    var.frontend_image,
  ]
}

run "reject_desired_count_outside_scaling_range" {
  command = plan

  variables {
    project_name          = "edu"
    vpc_id                = "vpc-0123456789abcdef0"
    private_subnet_ids    = ["subnet-0123456789abcdef0", "subnet-0fedcba9876543210"]
    alb_security_group_id = "sg-0123456789abcdef0"
    api_target_group_arn  = "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:targetgroup/edu-api/0123456789abcdef"
    web_target_group_arn  = "arn:aws:elasticloadbalancing:ap-northeast-1:123456789012:targetgroup/edu-web/0123456789abcdef"
    backend_image         = "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/edu-backend:abc1234"
    frontend_image        = "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/edu-frontend:abc1234"
    upload_bucket_arn     = "arn:aws:s3:::edu-production-uploads"
    backend_desired_count = 7
    backend_min_count     = 2
    backend_max_count     = 6
    common_environment    = {}
    secret_arns = {
      ANTHROPIC_API_KEY = "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:edu/anthropic-abc123"
      DATABASE_URL      = "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:edu/database-url-abc123"
      JWT_SECRET_KEY    = "arn:aws:ssm:ap-northeast-1:123456789012:parameter/edu/jwt-secret"
      REDIS_URL         = "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:edu/redis-url-abc123"
    }
  }

  expect_failures = [
    var.backend_desired_count,
  ]
}
