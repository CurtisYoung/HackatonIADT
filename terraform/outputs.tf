# Output definitions for Bedrock configuration

output "bedrock_model_arn" {
  value = aws_bedrock_model.diagram_analysis_model.model_arn
}

output "bedrock_endpoint_arn" {
  value = aws_bedrock_foundation_model_endpoint.diagram_analysis_endpoint.arn
}

output "provisioned_throughput_arn" {
  value = aws_bedrock_provisioned_throughput.diagram_analysis_throughput.arn
}
