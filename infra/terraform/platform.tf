resource "aws_s3_bucket_ownership_controls" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

data "aws_iam_policy_document" "bucket_transport" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.backups.arn, "${aws_s3_bucket.backups.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "backups" {
  bucket = aws_s3_bucket.backups.id
  policy = data.aws_iam_policy_document.bucket_transport.json
}

resource "aws_sqs_queue" "ingestion_dlq" {
  name                      = "${local.name}-${var.environment}-ingestion-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "ingestion" {
  name                       = "${local.name}-${var.environment}-ingestion"
  visibility_timeout_seconds = var.queue_visibility_timeout_seconds
  message_retention_seconds  = var.queue_message_retention_seconds
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingestion_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "ingestion" {
  queue_url = aws_sqs_queue.ingestion_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.ingestion.arn]
  })
}

resource "aws_sqs_queue" "analysis_dlq" {
  name                      = "${local.name}-${var.environment}-analysis-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "analysis" {
  name                       = "${local.name}-${var.environment}-analysis"
  visibility_timeout_seconds = var.queue_visibility_timeout_seconds
  message_retention_seconds  = var.queue_message_retention_seconds
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.analysis_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "analysis" {
  queue_url = aws_sqs_queue.analysis_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.analysis.arn]
  })
}

resource "aws_dynamodb_table" "control" {
  name         = "${local.name}-${var.environment}-control"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
}

resource "aws_scheduler_schedule_group" "ingestion" {
  name = "${local.name}-${var.environment}"
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${local.name}-${var.environment}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.ingestion.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "watchlist" {
  name       = "watchlist-ingestion"
  group_name = aws_scheduler_schedule_group.ingestion.name
  state      = var.ingestion_schedule_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window { mode = "OFF" }
  schedule_expression = var.ingestion_schedule_expression

  target {
    arn      = aws_sqs_queue.ingestion.arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      version    = 1
      job_id     = "scheduled-watchlist"
      action     = "sync_watchlist"
      created_at = "eventbridge-scheduler"
    })
    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
  }
}

resource "aws_ssm_document" "backup" {
  name            = "Atlas-Intelligence-Backup"
  document_type   = "Command"
  document_format = "YAML"
  content         = <<-YAML
    schemaVersion: '2.2'
    description: Create a consistent SQLite backup and upload it to the private Atlas S3 bucket.
    mainSteps:
      - action: aws:runShellScript
        name: backup
        inputs:
          timeoutSeconds: '600'
          runCommand:
            - |-
              set -euo pipefail
              docker inspect atlas-intelligence >/dev/null
              docker exec atlas-intelligence python -m server.backup --upload
  YAML
}

resource "aws_ssm_document" "status" {
  name            = "Atlas-Intelligence-Status"
  document_type   = "Command"
  document_format = "YAML"
  content         = <<-YAML
    schemaVersion: '2.2'
    description: Inspect Atlas containers, health, queues and dead-letter queues without a metrics service.
    mainSteps:
      - action: aws:runShellScript
        name: status
        inputs:
          timeoutSeconds: '120'
          runCommand:
            - |-
              set -euo pipefail
              docker ps --filter name=atlas
              curl -fsS http://127.0.0.1:8000/api/health
              for queue in \
                '${aws_sqs_queue.ingestion.url}' \
                '${aws_sqs_queue.analysis.url}' \
                '${aws_sqs_queue.ingestion_dlq.url}' \
                '${aws_sqs_queue.analysis_dlq.url}'; do
                aws sqs get-queue-attributes --region ${var.aws_region} --queue-url "$queue" \
                  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible ApproximateNumberOfMessagesDelayed
              done
  YAML
}
