output "kubernetes_api_server" {
  description = "Kubernetes API server endpoint"
  value       = "https://${google_container_cluster.this.endpoint}"
}

output "cluster_name" {
  value = google_container_cluster.this.name
}
