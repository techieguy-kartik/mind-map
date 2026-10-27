output "account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "existing_instance" {
  value = {
    id         = data.aws_instance.existing_host.id
    private_ip = data.aws_instance.existing_host.private_ip
    public_ip  = data.aws_instance.existing_host.public_ip
    state      = data.aws_instance.existing_host.instance_state
  }
}

output "ecr_repository_url" {
  value = aws_ecr_repository.atlas.repository_url
}

output "runtime_secret_arn" {
  value = aws_secretsmanager_secret.runtime.arn
}

output "backup_bucket" {
  value = aws_s3_bucket.backups.id
}

output "log_group" {
  value = aws_cloudwatch_log_group.application.name
}

output "ssm_deploy_document" {
  value = aws_ssm_document.deploy.name
}

output "private_access_command" {
  description = "Run after deployment; requires the existing SSH private key."
  value       = "ssh -L 8000:127.0.0.1:8000 ubuntu@${data.aws_instance.existing_host.public_ip}"
}
