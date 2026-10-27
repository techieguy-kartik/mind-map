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

output "ssm_deploy_document" {
  value = aws_ssm_document.deploy.name
}

output "ssm_backup_document" {
  value = aws_ssm_document.backup.name
}

output "ssm_status_document" {
  value = aws_ssm_document.status.name
}

output "ingestion_queue_url" {
  value = aws_sqs_queue.ingestion.url
}

output "analysis_queue_url" {
  value = aws_sqs_queue.analysis.url
}

output "dead_letter_queue_urls" {
  value = {
    ingestion = aws_sqs_queue.ingestion_dlq.url
    analysis  = aws_sqs_queue.analysis_dlq.url
  }
}

output "control_table" {
  value = aws_dynamodb_table.control.name
}

output "ingestion_schedule" {
  value = {
    name    = aws_scheduler_schedule.watchlist.name
    enabled = var.ingestion_schedule_enabled
  }
}

output "private_access_command" {
  description = "Run after deployment; requires the existing SSH private key."
  value       = "ssh -L 8000:127.0.0.1:8000 ubuntu@${data.aws_instance.existing_host.public_ip}"
}
