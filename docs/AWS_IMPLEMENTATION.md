# AWS implementation plan

## Current account status — 28 October 2026

The Atlas Terraform stack has been applied to AWS account `377131740229` in `us-east-1`: 13 resources added, zero existing resources changed, zero destroyed. Remote state uses `s3://news-agent-377131740229/atlas-intelligence/terraform.tfstate`. The referenced host is `nero-lab-engine` (`i-0c04d5f1a37d29ae0`); it remains owned by its original Terraform state.

The initially applied stack created ECR `atlas-intelligence`, backup bucket `atlas-intelligence-377131740229-us-east-1`, runtime secret `/atlas/production/runtime`, scoped IAM permissions, SSM core access, and deployment document `Atlas-Intelligence-Build-And-Deploy`. It also created a CloudWatch log group. The upgraded Terraform removes that log group and the `awslogs` driver; this removal takes effect when the owner applies the new plan.

The upgraded runtime uses three containers on the existing encrypted EC2 volume: API, ingestion worker and analysis worker. Terraform references the existing host without taking ownership of it and adds encrypted SQS queues, source-specific DLQs, a DynamoDB checkpoint table, S3 run manifests, EventBridge scheduling, IAM and SSM operations. Do not expose the development server directly to the internet.

## Pilot deployment

1. The SSM document clones the pushed Git repository, builds one checked-in Docker image, and starts the API plus two worker containers on the existing EC2 host.
2. Create a dedicated application directory and persistent encrypted EBS volume; do not reuse another project's database or queue.
3. Put `GROQ_API_KEY` and a random 24+ character `ATLAS_ACCESS_TOKEN` in Secrets Manager or an owner-readable environment file outside Git.
4. Run the container on EC2 loopback and access it through an SSH tunnel. Add a dedicated HTTPS hostname later without replacing unrelated Nginx routes. Set `ATLAS_SECURE_COOKIE=true` when HTTPS is enabled and back up the data volume to the dedicated S3 bucket.
5. Review SQS/DynamoDB usage and set an AWS account budget before enabling scheduled collection.

The schedule is intentionally disabled in Terraform until deployment is healthy. Manual GDELT collection becomes a durable queue job when AWS mode is configured, and investigations remain capped.

## Production transition

When the pilot passes its quality gates:

- Replace SQLite with private-subnet RDS PostgreSQL. Migrate canonical records before enabling multiple workers.
- Split the implemented ingestion queue into discovery, extraction and verification queues only when backlog measurements show separate scaling or retry policies are needed. Continue using idempotency keys for documents, events and material versions.
- Store only permitted raw evidence in versioned, encrypted S3 with source-specific retention.
- Run scheduled workers in ECS/Fargate or the existing EC2 capacity after measuring load.
- Use EventBridge schedules per connector; do not promise one universal real-time interval.
- Publish queue state, last source success, rejected records, Groq usage, investigation latency, and run manifests through the control table, health API, local structured logs, and private S3 records.
- Add point-in-time restore, restore drills, structured audit logs, and correction/retraction propagation.

Before provisioning new RDS, ECS, or managed-search resources, calculate and approve the incremental monthly AWS cost. Neptune and Bedrock are not part of this design.
