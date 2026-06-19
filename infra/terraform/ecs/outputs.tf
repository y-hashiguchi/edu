output "cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "task_security_group_id" {
  value = aws_security_group.tasks.id
}

output "backend_service_name" {
  value = aws_ecs_service.backend.name
}

output "backend_task_definition_arn" {
  value = aws_ecs_task_definition.backend.arn
}

output "worker_service_name" {
  value = aws_ecs_service.worker.name
}

output "worker_task_definition_arn" {
  value = aws_ecs_task_definition.worker.arn
}

output "frontend_service_name" {
  value = aws_ecs_service.frontend.name
}

output "frontend_task_definition_arn" {
  value = aws_ecs_task_definition.frontend.arn
}

output "backend_autoscaling_range" {
  value = {
    min = aws_appautoscaling_target.backend.min_capacity
    max = aws_appautoscaling_target.backend.max_capacity
  }
}

output "frontend_autoscaling_range" {
  value = {
    min = aws_appautoscaling_target.frontend.min_capacity
    max = aws_appautoscaling_target.frontend.max_capacity
  }
}

output "cloudwatch_alarm_names" {
  value = concat(
    [for alarm in aws_cloudwatch_metric_alarm.high_cpu : alarm.alarm_name],
    [for alarm in aws_cloudwatch_metric_alarm.running_tasks_low : alarm.alarm_name],
  )
}

output "deployment_lock_table_name" {
  value = aws_dynamodb_table.deployment_lock.name
}

output "migration_task_definition_arn" {
  description = "Run this task definition once before updating ECS services"
  value       = aws_ecs_task_definition.migration.arn
}

output "private_subnet_ids" {
  description = "Subnets to use in the aws ecs run-task network configuration"
  value       = var.private_subnet_ids
}

output "aws_region" {
  value = var.aws_region
}
