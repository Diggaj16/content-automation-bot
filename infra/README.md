# AWS deploy target

One EC2 instance running `docker-compose.prod.yml`, with images built and
pushed to ECR by GitHub Actions and deploys triggered over AWS SSM (no open
SSH port, no SSH keys in GitHub).

```
push to master
  -> CI (.github/workflows/ci.yml): lint, test, docker build check
  -> CD (.github/workflows/cd.yml): build+push images to ECR (via GitHub OIDC)
       -> SSM SendCommand to EC2: docker compose pull && up -d
```

## One-time setup

You need the AWS CLI + Terraform installed locally, with credentials for an
AWS account/role that can create IAM roles, an OIDC provider, ECR repos, and
an EC2 instance.

1. **Provision the AWS side:**

   ```
   cd infra/terraform
   terraform init
   terraform apply
   ```

   Review the plan — it creates:
   - 2 ECR repos (`content-automation-backend`, `content-automation-frontend`)
   - A GitHub OIDC provider + IAM role GitHub Actions assumes to push images
     and trigger deploys (no AWS keys stored in GitHub)
   - One EC2 instance (default `t3.large` — tune via `-var instance_type=...`
     if cost is a concern; two of the workers run headless Chromium and the
     stack is 7 containers, so don't go below `t3.medium`)
   - A security group exposing only 3000 (frontend) and 8000 (API) —
     restrict `allowed_http_cidrs` (defaults to `0.0.0.0/0`) to your office/VPN
     IP before applying if this shouldn't be open to the internet

   Note the outputs: `ecr_backend_repo_url`, `ecr_frontend_repo_url`,
   `github_deploy_role_arn`, `instance_id`, `instance_public_ip`.

2. **Configure GitHub** (repo Settings → Secrets and variables → Actions):

   | Type     | Name                  | Value                                  |
   |----------|-----------------------|------------------------------------------|
   | Secret   | `AWS_DEPLOY_ROLE_ARN` | `github_deploy_role_arn` output          |
   | Variable | `AWS_REGION`          | e.g. `ap-south-1`                        |
   | Variable | `EC2_INSTANCE_ID`     | `instance_id` output                     |
   | Variable | `DEPLOY_DIR`          | `/opt/content-automation`                |

3. **Put real secrets on the instance.** Terraform creates empty
   `backend.env` / `frontend.env` files on the box — it never touches them
   again, so they survive redeploys. Fill them in once via SSM Session
   Manager (no SSH needed):

   ```
   aws ssm start-session --target <instance_id>
   sudo nano /opt/content-automation/backend.env    # same keys as backend/.env.example
   sudo nano /opt/content-automation/frontend.env   # same keys as frontend/.env.local
   ```

4. **First deploy:** push to `master`. CI runs, then CD builds+pushes images
   and tells the instance (via SSM) to `docker compose pull && up -d`. Watch
   progress in the repo's Actions tab.

## Day-to-day

- Every push to `master` that passes CI auto-deploys.
- To check on the running stack: `aws ssm start-session --target <instance_id>`,
  then `cd /opt/content-automation && docker compose -f docker-compose.prod.yml ps`.
- Changing `docker-compose.prod.yml` structure (not just images) requires
  either re-running `terraform apply` (the instance's `user_data` embeds the
  file, so a change forces instance replacement) or manually editing the file
  on the box over SSM.
- Teardown: `terraform destroy` from `infra/terraform`.
