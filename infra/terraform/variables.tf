variable "aws_region" {
  description = "Region containing the existing EC2 host."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Local AWS CLI profile used by Terraform. CI should use role credentials and override this with an empty value."
  type        = string
  default     = "account2"
}

variable "environment" {
  description = "Atlas environment name."
  type        = string
  default     = "production"
}

variable "existing_instance_id" {
  description = "Existing EC2 instance managed by the Nero Terraform state. Atlas references but does not own it."
  type        = string
  default     = "i-0c04d5f1a37d29ae0"
}

variable "existing_instance_role_name" {
  description = "IAM role already attached to the existing EC2 instance."
  type        = string
  default     = "nero-lab-ec2-role"
}

variable "repository_url" {
  description = "Public Git repository cloned on EC2 by the SSM deployment document."
  type        = string
  default     = "https://github.com/techieguy-kartik/mind-map.git"
}

variable "backup_retention_days" {
  description = "Days before noncurrent backup objects expire."
  type        = number
  default     = 90

  validation {
    condition     = var.backup_retention_days >= 30
    error_message = "Backup retention must be at least 30 days."
  }
}

variable "raw_evidence_retention_days" {
  description = "Days to retain raw permitted evidence and run manifests in S3."
  type        = number
  default     = 365

  validation {
    condition     = var.raw_evidence_retention_days >= 90
    error_message = "Raw evidence retention must be at least 90 days."
  }
}

variable "ingestion_schedule_expression" {
  description = "EventBridge Scheduler expression for watchlist ingestion."
  type        = string
  default     = "rate(5 minutes)"
}

variable "ingestion_schedule_enabled" {
  description = "Enable scheduled ingestion after the worker containers are deployed and healthy."
  type        = bool
  default     = false
}

variable "crew_worker_enabled" {
  description = "Build the isolated Python 3.13 CrewAI analysis worker and expose specialist mode."
  type        = bool
  default     = false
}

variable "queue_message_retention_seconds" {
  description = "How long SQS retains unprocessed jobs."
  type        = number
  default     = 345600

  validation {
    condition     = var.queue_message_retention_seconds >= 86400 && var.queue_message_retention_seconds <= 1209600
    error_message = "Queue retention must be between 1 and 14 days."
  }
}

variable "queue_visibility_timeout_seconds" {
  description = "Worker lease for one SQS job."
  type        = number
  default     = 300

  validation {
    condition     = var.queue_visibility_timeout_seconds >= 60 && var.queue_visibility_timeout_seconds <= 43200
    error_message = "Queue visibility timeout must be between 60 seconds and 12 hours."
  }
}
