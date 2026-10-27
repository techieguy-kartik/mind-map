locals {
  name          = "atlas-intelligence"
  backup_bucket = "atlas-intelligence-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  common_path   = "/atlas/production"
}

resource "aws_ecr_repository" "atlas" {
  name                 = local.name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "atlas" {
  repository = aws_ecr_repository.atlas.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the 20 most recent release images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_s3_bucket" "backups" {
  bucket        = local.backup_bucket
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "expire-noncurrent-backups"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.backup_retention_days
    }
  }
}

resource "aws_secretsmanager_secret" "runtime" {
  name                    = "${local.common_path}/runtime"
  description             = "Atlas runtime JSON: GROQ_API_KEY and ATLAS_ACCESS_TOKEN. Terraform creates metadata only; values never enter state."
  recovery_window_in_days = 7
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/atlas/production/application"
  retention_in_days = 30
}

resource "aws_iam_policy" "host_runtime" {
  name        = "atlas-intelligence-host-runtime"
  description = "Least-privilege runtime access for Atlas on the existing EC2 host."
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuthorization"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "PullAtlasImages"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = aws_ecr_repository.atlas.arn
      },
      {
        Sid      = "ReadAtlasRuntimeSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.runtime.arn
      },
      {
        Sid    = "AtlasBackups"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.backups.arn,
          "${aws_s3_bucket.backups.arn}/*"
        ]
      },
      {
        Sid      = "AtlasApplicationLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:DescribeLogStreams", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.application.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "host_runtime" {
  role       = data.aws_iam_role.existing_host.name
  policy_arn = aws_iam_policy.host_runtime.arn
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = data.aws_iam_role.existing_host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_ssm_document" "deploy" {
  name            = "Atlas-Intelligence-Build-And-Deploy"
  document_type   = "Command"
  document_format = "YAML"

  content = <<-YAML
    schemaVersion: '2.2'
    description: Build Atlas from GitHub and run it privately on the existing EC2 host.
    parameters:
      GitRef:
        type: String
        default: main
        allowedPattern: '^[A-Za-z0-9._/-]{1,128}$'
      RepositoryUrl:
        type: String
        default: '${var.repository_url}'
        allowedPattern: '^https://github\\.com/techieguy-kartik/mind-map\\.git$'
    mainSteps:
      - action: aws:runShellScript
        name: buildAndDeploy
        inputs:
          timeoutSeconds: '1800'
          runCommand:
            - |-
              set -euo pipefail
              export DEBIAN_FRONTEND=noninteractive
              command -v git >/dev/null || { apt-get update -y && apt-get install -y git; }
              command -v docker >/dev/null || { curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && sh /tmp/get-docker.sh; }
              command -v aws >/dev/null || { apt-get update -y && apt-get install -y awscli; }
              command -v jq >/dev/null || { apt-get update -y && apt-get install -y jq; }
              systemctl enable --now docker
              install -d -m 0750 /opt/atlas /opt/atlas/data /etc/atlas
              rm -rf /opt/atlas/source.next
              git clone --depth 1 --branch '{{ GitRef }}' '{{ RepositoryUrl }}' /opt/atlas/source.next
              docker build --pull -t atlas-intelligence:current /opt/atlas/source.next
              aws secretsmanager get-secret-value --region ${var.aws_region} --secret-id '${aws_secretsmanager_secret.runtime.arn}' --query SecretString --output text > /etc/atlas/runtime.json
              chmod 0600 /etc/atlas/runtime.json
              jq -er '.GROQ_API_KEY // "" | "GROQ_API_KEY=" + .' /etc/atlas/runtime.json > /etc/atlas/atlas.env
              jq -er '.ATLAS_ACCESS_TOKEN | select(length >= 24) | "ATLAS_ACCESS_TOKEN=" + .' /etc/atlas/runtime.json >> /etc/atlas/atlas.env
              printf '%s\n' 'ATLAS_SECURE_COOKIE=false' 'ATLAS_DEMO=true' 'ATLAS_DAILY_INVESTIGATIONS=10' >> /etc/atlas/atlas.env
              chmod 0600 /etc/atlas/atlas.env
              docker rm -f atlas-intelligence >/dev/null 2>&1 || true
              docker run -d --name atlas-intelligence --restart unless-stopped \
                --env-file /etc/atlas/atlas.env \
                -e ATLAS_HOST=0.0.0.0 -e ATLAS_PORT=8000 -e ATLAS_DB=/app/var/atlas.sqlite3 \
                -p 127.0.0.1:8000:8000 \
                -v /opt/atlas/data:/app/var \
                --log-driver awslogs --log-opt awslogs-region=${var.aws_region} --log-opt awslogs-group=${aws_cloudwatch_log_group.application.name} \
                atlas-intelligence:current
              for attempt in $(seq 1 30); do
                if curl -fsS http://127.0.0.1:8000/api/health >/dev/null; then exit 0; fi
                sleep 2
              done
              docker logs atlas-intelligence --tail 100
              exit 1
  YAML
}
