variable "project_name" {
  description = "The name of the project."
  type        = string
  default = "${{ variables.CLUSTERNAME }}"
}

variable "region" {
  description = "The AWS region to deploy the EKS cluster."
  default     = "us-east-1" # N.Virginia
}

variable "kubernetes_version" {
  description = "The Kubernetes version for the EKS cluster."
  default     = "1.33"
}

variable "image_id" {
  description = "The AMI ID for the EKS cluster."
  default     = "ami-03db9f32eaa4c3c75" # Amazon EKS AMI. 
  #Can be updated to the latest version with aws cli command: 
  #aws ssm get-parameter --name /aws/service/eks/optimized-ami/1.31/amazon-linux-2023/x86_64/standard/recommended/image_id  --region us-east-1 --query "Parameter.Value" --output text'
}
#variable "rds_master_username" {
#  description = "The master username for the RDS instance."
#  type        = string
#  default     = "admin" # Optional default value
#}

#variable "rds_master_password" {
#  description = "The master password for the RDS instance."
#  type        = string
#  sensitive   = true
#}

variable "instance_type" {
  description = "instance tier"
  default = "m6i.large"
}

variable "vpc_cidr" {
  description = "The CIDR block for the VPC."
  default     = "10.0.0.0/16" # Optional default value 
}

