# Variable definitions for Bedrock configuration

variable "aws_region" {
  description = "AWS region where resources will be created"
  type        = string
  default     = "us-east-1"
}

variable "model_name" {
  description = "Name for the custom model"
  type        = string
  default     = "diagram-analysis-model"
}

variable "endpoint_name" {
  description = "Name for the Bedrock endpoint"
  type        = string
  default     = "diagram-analysis-endpoint"
}

variable "training_data_uri" {
  description = "S3 URI to the training data for the model"
  type        = string
  default     = "s3://diagram-analyzer-training-data/"
}

variable "provisioned_units" {
  description = "Number of provisioned throughput units for the model"
  type        = number
  default     = 1
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket to store model artifacts"
  type        = string
  default     = "diagram-analyzer-storage"
}
