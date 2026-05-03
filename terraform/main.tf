terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_iam_user" "bedrock_user" {
  name = "bedrock-inference-user"
  path = "/users/"
}

resource "aws_iam_access_key" "bedrock_key" {
  user = aws_iam_user.bedrock_user.name
}

resource "aws_iam_policy" "bedrock_policy" {
  name        = "${var.project_name}-bedrock-policy"
  description = "Permite acesso ao Amazon Bedrock"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/*",
          "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:inference-profile/*"
        ]
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "bedrock_attachment" {
  user       = aws_iam_user.bedrock_user.name
  policy_arn = aws_iam_policy.bedrock_policy.arn
}
