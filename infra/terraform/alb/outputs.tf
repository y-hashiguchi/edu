output "alb_dns_name" {
  description = "Create Route 53 ALIAS or CNAME records for app/api domains"
  value       = aws_lb.main.dns_name
}

output "alb_arn" {
  value = aws_lb.main.arn
}

output "app_security_group_id" {
  description = "Attach to EC2 instance (in addition to existing SGs)"
  value       = aws_security_group.app.id
}

output "api_target_group_arn" {
  value = aws_lb_target_group.api.arn
}

output "web_target_group_arn" {
  value = aws_lb_target_group.web.arn
}
