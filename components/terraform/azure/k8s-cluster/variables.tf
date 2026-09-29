variable "cluster_name" {
  description = "The name of the cluster (also used for resource group and DNS prefix)."
  type        = string
  validation {
    condition     = length(var.cluster_name) > 0
    error_message = "cluster_name is empty: set CLUSTER_NAME env var."
  }
}

variable "region" {
  description = "Azure location."
  default     = "eastus"
}

variable "kubernetes_version" {
  description = "AKS Kubernetes version; null = AKS default."
  default     = null
}

variable "instance_type" {
  description = "Node VM size."
  default     = "Standard_D2s_v5"
}

variable "node_count" {
  description = "Number of nodes in the default node pool."
  default     = 3
}
