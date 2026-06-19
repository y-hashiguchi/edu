output "backend_repository_url" {
  value = aws_ecr_repository.app["backend"].repository_url
}

output "frontend_repository_url" {
  value = aws_ecr_repository.app["frontend"].repository_url
}

output "repository_arns" {
  value = {
    for name, repository in aws_ecr_repository.app :
    name => repository.arn
  }
}

output "aws_region" {
  value = var.aws_region
}
