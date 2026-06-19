mock_provider "aws" {}

run "repository_plan" {
  command = plan

  variables {
    project_name = "edu"
  }

  assert {
    condition     = length(aws_ecr_repository.app) == 2
    error_message = "Backend and frontend repositories must both be created."
  }

  assert {
    condition = alltrue([
      for repository in aws_ecr_repository.app :
      repository.image_tag_mutability == "IMMUTABLE"
    ])
    error_message = "Release image tags must be immutable."
  }

  assert {
    condition = alltrue([
      for repository in aws_ecr_repository.app :
      repository.image_scanning_configuration[0].scan_on_push
    ])
    error_message = "All repositories must scan images on push."
  }
}
