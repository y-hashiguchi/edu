locals {
  tags = merge(
    {
      Project   = var.project_name
      ManagedBy = "Terraform"
    },
    var.tags,
  )

  upload_bucket_name = trimprefix(var.upload_bucket_arn, "arn:aws:s3:::")
  upload_prefix      = trim(var.upload_prefix, "/")

  managed_environment = {
    UPLOAD_STORAGE_BACKEND = "s3"
    S3_UPLOAD_BUCKET       = local.upload_bucket_name
    S3_UPLOAD_PREFIX       = local.upload_prefix
    S3_UPLOAD_REGION       = var.aws_region
  }

  runtime_environment = merge(var.common_environment, local.managed_environment)

  common_environment = [
    for name, value in local.runtime_environment : {
      name  = name
      value = value
    } if !contains(keys(var.secret_arns), name)
  ]

  common_secrets = [
    for name, value_from in var.secret_arns : {
      name      = name
      valueFrom = value_from
    } if !contains(keys(local.managed_environment), name)
  ]

  log_options = {
    awslogs-group         = aws_cloudwatch_log_group.app.name
    awslogs-region        = var.aws_region
    awslogs-stream-prefix = "ecs"
  }

  monitored_services = {
    backend = {
      service_name       = aws_ecs_service.backend.name
      minimum_task_count = var.backend_min_count
    }
    "grading-worker" = {
      service_name       = aws_ecs_service.worker.name
      minimum_task_count = var.worker_desired_count
    }
    frontend = {
      service_name       = aws_ecs_service.frontend.name
      minimum_task_count = var.frontend_min_count
    }
  }
}

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-prod"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project_name}-prod"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_dynamodb_table" "deployment_lock" {
  name         = "${var.project_name}-ecs-deployment-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "lock_name"

  attribute {
    name = "lock_name"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = local.tags
}

resource "aws_security_group" "tasks" {
  name        = "${var.project_name}-ecs-tasks"
  description = "Allow ALB traffic to ECS backend and frontend tasks"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Backend from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  ingress {
    description     = "Frontend from ALB"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_iam_role" "execution" {
  name = "${var.project_name}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "${var.project_name}-ecs-secrets"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "ssm:GetParameters",
        ]
        Resource = values(var.secret_arns)
      }],
      length(var.kms_key_arns) == 0 ? [] : [{
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = var.kms_key_arns
      }],
    )
  })
}

resource "aws_iam_role" "frontend_execution" {
  name = "${var.project_name}-ecs-frontend-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "frontend_execution" {
  role       = aws_iam_role.frontend_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name = "${var.project_name}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "task" {
  name = "${var.project_name}-ecs-app"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
        ]
        Resource = [var.upload_bucket_arn]
        Condition = {
          StringLike = {
            "s3:prefix" = [
              local.upload_prefix,
              "${local.upload_prefix}/*",
            ]
          }
        }
        }, {
        Effect = "Allow"
        Action = [
          "s3:DeleteObject",
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = ["${var.upload_bucket_arn}/${local.upload_prefix}/*"]
      }],
      var.enable_execute_command ? [{
        Effect = "Allow"
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel",
        ]
        Resource = ["*"]
      }] : [],
    )
  })
}

resource "aws_iam_role" "frontend_task" {
  count = var.enable_execute_command ? 1 : 0
  name  = "${var.project_name}-ecs-frontend-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "frontend_exec" {
  count = var.enable_execute_command ? 1 : 0
  name  = "${var.project_name}-ecs-frontend-exec"
  role  = aws_iam_role.frontend_task[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel",
      ]
      Resource = ["*"]
    }]
  })
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = var.backend_image
    essential = true
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    environment = local.common_environment
    secrets     = local.common_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options   = local.log_options
    }
    linuxParameters = {
      initProcessEnabled = true
    }
  }])

  tags = local.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-grading-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name        = "grading-worker"
    image       = var.backend_image
    essential   = true
    command     = ["uv", "run", "arq", "app.worker.settings.WorkerSettings"]
    environment = local.common_environment
    secrets     = local.common_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options   = local.log_options
    }
    linuxParameters = {
      initProcessEnabled = true
    }
  }])

  tags = local.tags
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.frontend_execution.arn
  task_role_arn            = var.enable_execute_command ? aws_iam_role.frontend_task[0].arn : null

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = var.frontend_image
    essential = true
    portMappings = [{
      containerPort = 80
      hostPort      = 80
      protocol      = "tcp"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options   = local.log_options
    }
    linuxParameters = {
      initProcessEnabled = true
    }
  }])

  tags = local.tags
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "${var.project_name}-backend-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name        = "backend"
    image       = var.backend_image
    essential   = true
    command     = ["uv", "run", "alembic", "upgrade", "head"]
    environment = local.common_environment
    secrets     = local.common_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options   = local.log_options
    }
  }])

  tags = local.tags
}

resource "aws_ecs_service" "backend" {
  name                   = "backend"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = aws_ecs_task_definition.backend.arn
  desired_count          = var.backend_desired_count
  launch_type            = "FARGATE"
  enable_execute_command = var.enable_execute_command

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 60

  network_configuration {
    assign_public_ip = false
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.tasks.id]
  }

  load_balancer {
    target_group_arn = var.api_target_group_arn
    container_name   = "backend"
    container_port   = 8000
  }

  lifecycle {
    ignore_changes = [
      desired_count,
      task_definition,
    ]
  }

  tags = local.tags
}

resource "aws_ecs_service" "worker" {
  name                   = "grading-worker"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = aws_ecs_task_definition.worker.arn
  desired_count          = var.worker_desired_count
  launch_type            = "FARGATE"
  enable_execute_command = var.enable_execute_command

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    assign_public_ip = false
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.tasks.id]
  }

  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = local.tags
}

resource "aws_ecs_service" "frontend" {
  name                   = "frontend"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = aws_ecs_task_definition.frontend.arn
  desired_count          = var.frontend_desired_count
  launch_type            = "FARGATE"
  enable_execute_command = var.enable_execute_command

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 30

  network_configuration {
    assign_public_ip = false
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.tasks.id]
  }

  load_balancer {
    target_group_arn = var.web_target_group_arn
    container_name   = "frontend"
    container_port   = 80
  }

  lifecycle {
    ignore_changes = [
      desired_count,
      task_definition,
    ]
  }

  tags = local.tags
}

resource "aws_appautoscaling_target" "backend" {
  max_capacity       = var.backend_max_count
  min_capacity       = var.backend_min_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "backend_cpu" {
  name               = "${var.project_name}-backend-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = var.autoscaling_cpu_target
    scale_in_cooldown  = var.autoscaling_scale_in_cooldown
    scale_out_cooldown = var.autoscaling_scale_out_cooldown

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

resource "aws_appautoscaling_target" "frontend" {
  max_capacity       = var.frontend_max_count
  min_capacity       = var.frontend_min_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.frontend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "frontend_cpu" {
  name               = "${var.project_name}-frontend-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.frontend.resource_id
  scalable_dimension = aws_appautoscaling_target.frontend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.frontend.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = var.autoscaling_cpu_target
    scale_in_cooldown  = var.autoscaling_scale_in_cooldown
    scale_out_cooldown = var.autoscaling_scale_out_cooldown

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  for_each = local.monitored_services

  alarm_name        = "${var.project_name}-${each.key}-high-cpu"
  alarm_description = "${each.key} average CPU remains above ${var.cpu_alarm_threshold}%"
  namespace         = "AWS/ECS"
  metric_name       = "CPUUtilization"
  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = each.value.service_name
  }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  threshold           = var.cpu_alarm_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "missing"
  alarm_actions       = var.alarm_action_arns
  ok_actions          = var.alarm_action_arns

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "running_tasks_low" {
  for_each = local.monitored_services

  alarm_name        = "${var.project_name}-${each.key}-running-tasks-low"
  alarm_description = "${each.key} running task count is below its configured minimum"
  namespace         = "ECS/ContainerInsights"
  metric_name       = "RunningTaskCount"
  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = each.value.service_name
  }
  statistic           = "Minimum"
  period              = 60
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  threshold           = each.value.minimum_task_count
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = var.alarm_action_arns
  ok_actions          = var.alarm_action_arns

  tags = local.tags
}
