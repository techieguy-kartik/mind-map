# AWS implementation plan

## Current account status — 28 October 2026

The Atlas Terraform stack has been applied to AWS account `377131740229` in `us-east-1`: 13 resources added, zero existing resources changed, zero destroyed. Remote state uses `s3://news-agent-377131740229/atlas-intelligence/terraform.tfstate`. The referenced host is `nero-lab-engine` (`i-0c04d5f1a37d29ae0`); it remains owned by its original Terraform state.

Created resources include ECR `atlas-intelligence`, backup bucket `atlas-intelligence-377131740229-us-east-1`, runtime secret `/atlas/production/runtime`, log group `/atlas/production/application`, scoped IAM permissions, SSM core access, and deployment document `Atlas-Intelligence-Build-And-Deploy`.

The checked-in pilot runs as one container with SQLite on the existing encrypted EC2 volume. Terraform under `infra/terraform` references the existing host without taking ownership of it and creates Atlas-specific ECR, backup, secret, logging, IAM, and SSM deployment resources. Do not expose the development server directly to the internet.

## Pilot deployment

1. The SSM document clones the pushed Git repository and builds the checked-in Dockerfile on the existing EC2 host.
2. Create a dedicated application directory and persistent encrypted EBS volume; do not reuse another project's database or queue.
3. Put `GROQ_API_KEY` and a random 24+ character `ATLAS_ACCESS_TOKEN` in Secrets Manager or an owner-readable environment file outside Git.
4. Run the container on EC2 loopback and access it through an SSH tunnel. Add a dedicated HTTPS hostname later without replacing unrelated Nginx routes. Set `ATLAS_SECURE_COOKIE=true` when HTTPS is enabled and back up the data volume to the dedicated S3 bucket.
5. Set an AWS budget and alarms before enabling scheduled collection.

The pilot is intentionally manual: GDELT collection is user-triggered and investigations are capped. This makes quota, precision, and usefulness measurable before paying for a larger pipeline.

## Production transition

When the pilot passes its quality gates:

- Replace SQLite with private-subnet RDS PostgreSQL. Migrate canonical records before enabling multiple workers.
- Create separate SQS queues for discovery, extraction, verification, and investigation plus dead-letter queues. Use idempotency keys for document, event, and material version.
- Store only permitted raw evidence in versioned, encrypted S3 with source-specific retention.
- Run scheduled workers in ECS/Fargate or the existing EC2 capacity after measuring load.
- Use EventBridge schedules per connector; do not promise one universal real-time interval.
- Publish queue age, last source success, rejected records, Groq usage, investigation latency, and budget to CloudWatch.
- Add point-in-time restore, restore drills, structured audit logs, and correction/retraction propagation.

Before provisioning new RDS, ECS, or managed-search resources, calculate and approve the incremental monthly AWS cost. Neptune and Bedrock are not part of this design.
