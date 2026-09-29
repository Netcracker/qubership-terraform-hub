variable "cluster_name" {
  description = "The name of the cluster (also used for network and labels)."
  type        = string
  validation {
    condition     = length(var.cluster_name) > 0
    error_message = "cluster_name is empty: set CLUSTER_NAME env var."
  }
}

variable "region" {
  description = "GCP region for the regional GKE cluster."
  default     = "us-east1"
}

variable "kubernetes_version" {
  description = "Minimum GKE master version; null = GKE default."
  default     = null
}

variable "instance_type" {
  description = "Node machine type."
  default     = "e2-standard-2"
}

variable "node_count" {
  description = "Nodes PER ZONE (regional cluster spans 3 zones, so 1 = 3 nodes)."
  default     = 1
}

variable "vpc_cidr" {
  description = "CIDR split into node subnet, pod and service ranges."
  default     = "10.0.0.0/16"
}
