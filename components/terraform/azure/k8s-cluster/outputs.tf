output "kubernetes_api_server" {
  description = "Kubernetes API server endpoint"
  value       = "https://${azurerm_kubernetes_cluster.this.fqdn}"
}

output "cluster_name" {
  value = azurerm_kubernetes_cluster.this.name
}

# Client-certificate kubeconfig (local accounts); no az/kubelogin needed
output "kubeconfig" {
  value     = azurerm_kubernetes_cluster.this.kube_config_raw
  sensitive = true
}

output "ingress_ip" {
  description = "Static public IP for LoadBalancer services"
  value       = azurerm_public_ip.ingress.ip_address
}
