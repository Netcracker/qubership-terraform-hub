variable "cluster_name" {
  description = "The name of the cluster (also used for VPC, tags and IAM role names)."
  type        = string
  validation {
    condition     = length(var.cluster_name) > 0
    error_message = "cluster_name is empty: set CLUSTER_NAME env var."
  }
}

variable "region" {
  description = "The AWS region to deploy the EKS cluster."
  default     = "us-east-1" # N.Virginia
}

variable "kubernetes_version" {
  description = "The Kubernetes version for the EKS cluster. null = keep the current one (new cluster: EKS default)."
  type        = string
  default     = null
}

variable "instance_type" {
  description = "instance tier"
  default     = "m6i.large"
}

variable "node_count" {
  description = "Desired (and minimum) number of worker nodes; max is node_count + 1."
  default     = 3
}

variable "vpc_cidr" {
  description = "The CIDR block for the VPC."
  default     = "10.0.0.0/16"
}
