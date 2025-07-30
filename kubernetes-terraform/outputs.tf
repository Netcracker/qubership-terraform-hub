output "vpc_id" {
  description = "The ID of the VPC."
  value       = module.vpc.vpc_id
}

output "public_subnets" {
  description = "The public subnets."
  value       = module.vpc.public_subnets
}

output "private_subnets" {
  description = "The private subnets."
  value       = module.vpc.private_subnets
}

output "kubernetes_api_server" {
  description = "Kubernetes API server endpoint"
  value       = module.eks_al2023.cluster_endpoint
}



