provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Application = "atlas-intelligence"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Repository  = "techieguy-kartik/mind-map"
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_instance" "existing_host" {
  instance_id = var.existing_instance_id
}

data "aws_iam_role" "existing_host" {
  name = var.existing_instance_role_name
}
