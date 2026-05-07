output "access_key_id" {
  description = "AWS Access Key ID"
  value       = aws_iam_access_key.bedrock_key.id
}

output "secret_access_key" {
  description = "AWS Secret Access Key"
  value       = aws_iam_access_key.bedrock_key.secret
  sensitive   = true
}

output "user_arn" {
  description = "IAM User ARN"
  value       = aws_iam_user.bedrock_user.arn
}

output "region" {
  description = "AWS Region"
  value       = data.aws_region.current.name
}
