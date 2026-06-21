variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Short name used as a prefix for created resources"
  type        = string
  default     = "content-automation"
}

variable "github_repo" {
  description = "GitHub repo allowed to assume the deploy role, as \"owner/repo\""
  type        = string
  default     = "Diggaj16/content-automation-bot"
}

variable "instance_type" {
  description = "EC2 instance size. The stack runs postgres + redis + api + one unified arq worker + frontend (5 containers); the worker and api containers run Playwright/Chromium."
  type        = string
  default     = "t3a.large"
}

variable "deploy_dir" {
  description = "Directory on the EC2 instance the stack is deployed into"
  type        = string
  default     = "/opt/content-automation"
}

variable "allowed_http_cidrs" {
  description = "CIDRs allowed to reach the frontend (3000) and API (8000) ports"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "root_volume_gb" {
  description = "Root EBS volume size — Playwright/Chromium images are large"
  type        = number
  default     = 40
}
