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
   - One EC2 instance (default `t3a.large` — tune via `-var instance_type=...`
     if cost is a concern; the stack is 5 containers — postgres, redis, api,
     a unified arq worker, frontend — and the worker plus api containers run
     headless Chromium, so don't go below `t3a.medium`)
   - A security group exposing only 80/443 to the internet, fronted by Caddy
     — neither the frontend (3000) nor the API (8000) is reachable directly;
     Caddy terminates TLS and reverse-proxies to the frontend over the
     internal Docker network, which in turn reaches the API the same way.
     Restrict `allowed_http_cidrs` (defaults to `0.0.0.0/0`) to your office/VPN
     IP before applying if even the public site shouldn't be open to the whole
     internet, or set `BASIC_AUTH_USER` / `BASIC_AUTH_PASSWORD` in
     `frontend.env` (step 3) to put an HTTP Basic Auth prompt in front of it
     instead (see `frontend/proxy.ts`)
   - A fixed Elastic IP, so the public address survives instance replacement
     (e.g. from a future `user_data` change). Caddy auto-provisions a free
     Let's Encrypt cert for `<ip-with-dashes>.sslip.io`, which resolves to that
     IP with zero DNS setup — see the `app_domain` / `app_url` outputs.

   Note the outputs: `ecr_backend_repo_url`, `ecr_frontend_repo_url`,
   `github_deploy_role_arn`, `instance_id`, `instance_public_ip`, `app_domain`,
   `app_url`.

   This particular apply (adding the Elastic IP + Caddy) replaces the existing
   EC2 instance — `user_data` changes force replacement — so the IP **will
   change** from whatever it was before. Use the post-apply `instance_public_ip`
   / `app_domain` outputs, not any IP noted earlier.

2. **Configure GitHub** (repo Settings → Secrets and variables → Actions):

   | Type     | Name                  | Value                                  |
   |----------|-----------------------|------------------------------------------|
   | Secret   | `AWS_DEPLOY_ROLE_ARN` | `github_deploy_role_arn` output          |
   | Variable | `AWS_REGION`          | e.g. `ap-south-1`                        |
   | Variable | `EC2_INSTANCE_ID`     | `instance_id` output                     |
   | Variable | `DEPLOY_DIR`          | `/opt/content-automation`                |
   | Variable | `DOMAIN`              | `app_domain` output (or your own domain) |

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
