# AWS EKS reference module for FuzeBox AEOS.
#
# This module provisions the cluster and the IAM role that the Cosigner API
# assumes via IRSA so that the KMSProvider can sign without long-lived keys.
# Customers usually fork it for their own VPC layout — this is the reference.

terraform {
  required_providers {
    aws        = { source = "hashicorp/aws", version = "~> 5.0" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.20" }
    helm       = { source = "hashicorp/helm", version = "~> 2.10" }
  }
  required_version = ">= 1.5"
}

variable "cluster_name"      { type = string }
variable "region"            { type = string  default = "us-east-1" }
variable "vpc_id"            { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "tenant"            { type = string }

resource "aws_iam_role" "fuzebox_cosigner" {
  name = "${var.cluster_name}-fuzebox-cosigner"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.eks.arn }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" =
            "system:serviceaccount:fuzebox:cosigner-api"
        }
      }
    }]
  })
}

resource "aws_kms_key" "fuzebox_signing" {
  description              = "FuzeBox AEOS PEL row signing — ${var.tenant}"
  customer_master_key_spec = "ECC_NIST_P256"
  key_usage                = "SIGN_VERIFY"
  enable_key_rotation      = false   # KMS auto-rotates ECC keys yearly
  deletion_window_in_days  = 30
}

resource "aws_iam_role_policy" "fuzebox_cosigner_kms" {
  role = aws_iam_role.fuzebox_cosigner.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["kms:Sign", "kms:Verify", "kms:GetPublicKey"]
      Resource = aws_kms_key.fuzebox_signing.arn
    }]
  })
}

# Customer brings the EKS cluster + OIDC provider; we just reference them.
data "aws_eks_cluster" "this" { name = var.cluster_name }
resource "aws_iam_openid_connect_provider" "eks" {
  url            = data.aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = ["9e99a48a9960b14926bb7f3b02e22da2b0ab7280"]
}

output "kms_key_id"   { value = aws_kms_key.fuzebox_signing.key_id }
output "service_role" { value = aws_iam_role.fuzebox_cosigner.arn }
