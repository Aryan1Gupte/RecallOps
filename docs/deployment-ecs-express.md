# RecallOps ECS Express Deployment

RecallOps is deployed for the public demo on AWS ECS Express Mode in `us-east-1`.
App Runner was not used because new App Runner customer onboarding was
unavailable for this AWS account.

Current deployed state:

- Public URL: `https://re-13632ec1844d486cbc3ab2f88ac2b387.ecs.us-east-1.on.aws`
- ECS cluster: `default`
- ECS Express service: `recallops-demo`
- ECR repository: `recallops`
- ECR image tag: `m18-659fd0c`
- Database secret location: SSM Parameter Store SecureString at `/recallops/prod/DATABASE_URL`
- Runtime region: `us-east-1`
- Bedrock models: Nova Lite for recommendations, Titan Embeddings for vectors

The deployment architecture is:

```text
Docker image -> ECR -> ECS Express public service -> CockroachDB Cloud + Bedrock
```

Local AWS CLI commands create and update AWS resources remotely. After deployment,
the app runs inside AWS ECS, not from the developer laptop.

## Prerequisites

- AWS CLI authenticated to the target AWS account.
- Access to `us-east-1`.
- An ECR repository named `recallops`.
- A built Docker image for the current source state.
- CockroachDB migrations applied before cutover.
- CockroachDB `DATABASE_URL` stored as an SSM SecureString.
- IAM roles for ECS infrastructure, task execution, and the running task.
- Bedrock model access for Nova Lite and Titan Embeddings in `us-east-1`.

Never commit `.env`, `DATABASE_URL`, AWS credentials, MCP client configuration,
private keys, or copied console snippets containing secret values.

## Pre-Deploy Migration

Run Alembic manually before deploying or cutting over a new image. The container
does not run migrations in its `CMD` or FastAPI startup.

From the repository root, with the ignored local environment loaded safely:

```bash
cd backend
alembic upgrade head
```

If the migration command reads `DATABASE_URL` from a local `.env`, keep that file
ignored and never paste its contents into logs, issues, docs, or chat.

## Build and Push Image

Build the production image from the repository root:

```bash
docker build -t recallops:local .
```

Tag the image for ECR with the deployment tag:

```bash
docker tag recallops:local <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/recallops:m18-659fd0c
```

Authenticate Docker to ECR and push:

```bash
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/recallops:m18-659fd0c
```

Do not put AWS access keys or database credentials into the image. The Docker
image already includes the public CockroachDB CA certificate at
`/root/.postgresql/root.crt` so `sslmode=verify-full` works in ECS.

## DATABASE_URL Secret

The deployed service reads `DATABASE_URL` from SSM Parameter Store SecureString:

```text
/recallops/prod/DATABASE_URL
```

Use the AWS Console or a careful CLI command with a placeholder value:

```bash
aws ssm put-parameter \
  --name /recallops/prod/DATABASE_URL \
  --type SecureString \
  --value '<DATABASE_URL>' \
  --overwrite \
  --region us-east-1
```

Avoid leaving the real value in shell history. Do not print the parameter value
or store it in plain-text ECS environment variables.

## IAM Roles

Use separate roles for the deployment responsibilities:

- **ECS infrastructure role**: lets ECS Express manage the public service
  infrastructure it creates for the service.
- **ECS task execution role**: lets ECS pull the private ECR image and write
  container logs.
- **ECS task role**: grants the running RecallOps container only the permissions
  it needs at runtime.

The task role needs:

- Permission to read `/recallops/prod/DATABASE_URL` from SSM Parameter Store.
- Permission to invoke the configured Bedrock Nova Lite and Titan Embeddings
  models, for example `bedrock:InvokeModel` scoped to the selected model
  resources when possible.

Do not configure static AWS keys in container environment variables.

## ECS Express Service

The public demo service was created in:

```text
ECS -> Clusters -> default -> Services -> recallops-demo
```

The service should use:

- Image: `<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/recallops:m18-659fd0c`
- Container port: `8000`
- Public ingress enabled through ECS Express
- SSM SecureString mapped to the container as `DATABASE_URL`
- Task role with Bedrock and SSM read access
- Task execution role with ECR/logging access

Required runtime environment:

```text
APP_ENV=production
AWS_REGION=us-east-1
BEDROCK_CHAT_MODEL_ID=<nova-lite-model-or-inference-profile-id>
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
RECALL_OPS_ENABLE_API_DOCS=false
RECALL_OPS_ENABLE_AI_RATE_LIMIT=true
RECALL_OPS_AI_RATE_LIMIT_REQUESTS=10
RECALL_OPS_AI_RATE_LIMIT_WINDOW_SECONDS=60
RECALL_OPS_TRUST_PROXY_HEADERS=false
```

Do not set `PORT` unless the deployment explicitly requires overriding the image
default. The image defaults to `8000`.

## Public Smoke Test

Run these checks after deployment:

```bash
curl -i https://re-13632ec1844d486cbc3ab2f88ac2b387.ecs.us-east-1.on.aws/api/health
curl -i https://re-13632ec1844d486cbc3ab2f88ac2b387.ecs.us-east-1.on.aws/api/health/database
curl -i https://re-13632ec1844d486cbc3ab2f88ac2b387.ecs.us-east-1.on.aws/docs
curl -i https://re-13632ec1844d486cbc3ab2f88ac2b387.ecs.us-east-1.on.aws/openapi.json
```

Expected:

- `/api/health` returns `200`
- `/api/health/database` returns `200`
- `/docs` returns `404`
- `/openapi.json` returns `404`
- The public UI loads
- Recall similar memories works
- Memory-assisted recommendation works
- Memory Inspector works
- Raw vectors are not displayed or returned publicly

## Cleanup After Judging

Keep the ECS Express service deployed during judging. After judging ends, delete
the service if the demo no longer needs to stay public.

Use the service ARN from the AWS Console or CLI:

```bash
aws ecs delete-express-gateway-service \
  --service-arn <SERVICE_ARN> \
  --region us-east-1
```

Deleting the ECS Express service should remove associated managed Express
service resources such as load balancer, target groups, security groups,
autoscaling policies, and related managed infrastructure. Verify in the AWS
Console that no unexpected resources remain.

Optional cleanup after judging:

- ECR image tag `m18-659fd0c`
- ECR repository `recallops`, if no longer needed
- SSM parameter `/recallops/prod/DATABASE_URL`
- IAM roles and inline/attached policies created for the demo
- CloudWatch log groups created by the ECS service
- CockroachDB cluster, if no longer needed

Do not delete shared infrastructure or non-demo resources without reviewing
dependencies first.

## Cost Notes

The ECS Express service should remain deployed while judges may access it.
Keeping it running may consume AWS credits or costs from ECS/Fargate capacity,
managed public ingress infrastructure, CloudWatch logs, Bedrock calls, and ECR
image storage. CockroachDB Cloud may also incur cost depending on the cluster
plan.

Keep AWS Budgets alerts enabled. Delete the ECS Express service after judging if
the public demo no longer needs to remain available.

## Final Submission Checklist

- Public GitHub repository is up to date and includes a license.
- Public deployed demo URL is included in the submission.
- Under-3-minute public YouTube or Vimeo demo video is uploaded.
- Devpost description explains the problem, solution, architecture, and demo
  story.
- CockroachDB tools used are listed:
  - CockroachDB Distributed Vector Indexing
  - CockroachDB Cloud Managed MCP Server
- AWS services used are listed:
  - ECS Express Mode
  - ECR
  - SSM Parameter Store SecureString
  - IAM roles
  - CloudWatch logs
  - Bedrock Nova Lite
  - Titan Embeddings
- Smoke test passes immediately before submitting.
- No `.env`, database URLs, AWS credentials, MCP configs, private keys, raw
  vectors, provider payloads, stack traces, or account-specific secret snippets
  are committed or shown in the demo.
