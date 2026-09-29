output "kubernetes_api_server" {
  description = "Kubernetes API server endpoint"
  value       = "https://${azurerm_kubernetes_cluster.this.fqdn}"
}

output "cluster_name" {
  value = azurerm_kubernetes_cluster.this.name
}
