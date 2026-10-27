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
