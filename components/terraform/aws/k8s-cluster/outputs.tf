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
  value       = module.eks.cluster_endpoint
}

output "cluster_name" {
  value = module.eks.cluster_name
}


# No secrets inside: token comes from `aws eks get-token` at call time
output "kubeconfig" {
  value = yamlencode({
    apiVersion      = "v1"
    kind            = "Config"
    current-context = module.eks.cluster_name
    clusters        = [{ name = module.eks.cluster_name, cluster = { server = module.eks.cluster_endpoint, certificate-authority-data = module.eks.cluster_certificate_authority_data } }]
    contexts        = [{ name = module.eks.cluster_name, context = { cluster = module.eks.cluster_name, user = module.eks.cluster_name } }]
    users = [{ name = module.eks.cluster_name, user = { exec = {
      apiVersion = "client.authentication.k8s.io/v1beta1"
      command    = "aws"
      args       = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.region, "--output", "json"]
    } } }]
  })
}
