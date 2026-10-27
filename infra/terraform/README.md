# Atlas Terraform

This stack references the existing `nero-lab-engine` EC2 instance but does not own or modify the instance, Elastic IP, VPC, subnet, root volume, key pair, or security group. Those remain in the existing Nero Terraform state.

Atlas owns:

- private ECR repository and retention policy;
- encrypted, versioned S3 backup bucket;
- Secrets Manager secret metadata (values are inserted out of band, never enter Terraform state, and are fetched directly by containers through the EC2 role);
- encrypted ingestion and analysis queues with separate dead-letter queues;
- an on-demand DynamoDB control/checkpoint table with point-in-time recovery;
- a disabled-by-default EventBridge ingestion schedule;
- least-privilege instance and scheduler roles;
- SSM deployment and consistent-backup documents.

CloudWatch is intentionally not used. Containers use size-limited local JSON logs, durable job state is kept in DynamoDB, failed work is visible in SQS dead-letter queues, and backups/run artifacts stay in private S3.

Initialize and review:

```bash
cp backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl
terraform fmt -check
terraform validate
terraform plan -out=atlas.tfplan
terraform apply atlas.tfplan
```

The ingestion schedule defaults to disabled. Deploy and verify all three containers before setting `ingestion_schedule_enabled = true`.

The SSM deployment document passes only `ATLAS_RUNTIME_SECRET_ID` to the containers. The API and workers call `GetSecretValue` through the instance IAM role during startup; no credential is copied into `/etc/atlas`, Docker command arguments, or Terraform state.

After apply, insert runtime secrets without printing them:

```bash
read -s -p 'Groq API key: ' GROQ_API_KEY; printf '\n'
read -s -p 'Atlas access token (24+ chars): ' ATLAS_ACCESS_TOKEN; printf '\n'
jq -n --arg groq "$GROQ_API_KEY" --arg token "$ATLAS_ACCESS_TOKEN" \
  '{GROQ_API_KEY:$groq,ATLAS_ACCESS_TOKEN:$token}' > /tmp/atlas-runtime.json
aws secretsmanager put-secret-value --profile account2 --region us-east-1 \
  --secret-id /atlas/production/runtime --secret-string file:///tmp/atlas-runtime.json
shred -u /tmp/atlas-runtime.json
unset GROQ_API_KEY ATLAS_ACCESS_TOKEN
```

Start the existing instance, wait for it to register with SSM, then deploy the pushed `main` branch:

```bash
aws ec2 start-instances --profile account2 --region us-east-1 --instance-ids i-0c04d5f1a37d29ae0
aws ec2 wait instance-running --profile account2 --region us-east-1 --instance-ids i-0c04d5f1a37d29ae0
aws ssm send-command --profile account2 --region us-east-1 \
  --instance-ids i-0c04d5f1a37d29ae0 \
  --document-name Atlas-Intelligence-Build-And-Deploy \
  --parameters GitRef=main
```

The container listens only on EC2 loopback. Access it privately:

```bash
ssh -i /path/to/nero-lab-key.pem -L 8000:127.0.0.1:8000 ubuntu@100.26.129.195
```

Then open `http://127.0.0.1:8000`. This stack deliberately does not alter the broad legacy security group or overwrite the server's current Nginx configuration.
