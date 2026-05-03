# Terraform configuration for Bedrock access

provider "aws" {
  region = var.aws_region
}

# Create a custom model endpoint for our diagram analysis
resource "aws_bedrock_model" "diagram_analysis_model" {
  model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

  model_name = var.model_name
  description = "Custom model for diagram analysis and security evaluation"

  # This creates a custom model endpoint
  inference_configuration {
    inference_parameter {
      name  = "max_tokens"
      value = "3072"
    }
    inference_parameter {
      name  = "temperature"
      value = "0.7"
    }
    inference_parameter {
      name  = "top_p"
      value = "0.95"
    }
    inference_parameter {
      name  = "top_k"
      value = "50"
    }
    inference_parameter {
      name  = "stop_sequences"
      value = "\"END\""
    }
  }
}

# Create a custom model version
resource "aws_bedrock_custom_model_version" "diagram_analysis_version" {
  model_id      = aws_bedrock_model.diagram_analysis_model.id
  model_version = "v1"

  training_data_config {
    data_source {
      s3_data_source {
        uri = var.training_data_uri
      }
    }
  }
}

# Create a provisioned throughput for model inference
resource "aws_bedrock_provisioned_throughput" "diagram_analysis_throughput" {
  model_id = aws_bedrock_model.diagram_analysis_model.id

  provisioned_throughput_inference_units = var.provisioned_units

  # Set auto scaling for dynamic throughput
  auto_scaling {
    min_provisioned_throughput_inference_units_per_model = 1
    max_provisioned_throughput_inference_units_per_model = 10
    target_utilization_percentage = 70
  }
}

# Create a foundation model endpoint
resource "aws_bedrock_foundation_model_endpoint" "diagram_analysis_endpoint" {
  model_id = aws_bedrock_model.diagram_analysis_model.id

  endpoint_name = var.endpoint_name

  visibility = "PRIVATE"

  # Use the custom model version
  model_version = aws_bedrock_custom_model_version.diagram_analysis_version.model_version

  # Configure associated authentication
  auth_mode = "IAM"

  # Add the S3 bucket policy to allow Bedrock to access the model artifacts
  additional_models_config {
    model_id = "rhosullivan.alembic-model-v1"
    model_version = "v1"
    model_artifacts = "s3://bucket-name/model-artifacts"
  }
}

# Create a data access policy for the Bedrock endpoint
resource "aws_s3_bucket_policy" "bedrock_access_policy" {
  bucket = var.s3_bucket_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action   = [
          "s3:GetObject"
        ]
        Resource = "${var.s3_bucket_name}/*"
      }
    ]
  })
}
