output "kubernetes_api_server" {
  description = "Kubernetes API server endpoint"
  value       = "https://${google_container_cluster.this.endpoint}"
}

output "cluster_name" {
  value = google_container_cluster.this.name
}

# No secrets inside: token comes from gke-gcloud-auth-plugin at call time
output "kubeconfig" {
  value = yamlencode({
    apiVersion      = "v1"
    kind            = "Config"
    current-context = google_container_cluster.this.name
    clusters = [{ name = google_container_cluster.this.name, cluster = {
      server                     = "https://${google_container_cluster.this.endpoint}"
      certificate-authority-data = google_container_cluster.this.master_auth[0].cluster_ca_certificate
    } }]
    contexts = [{ name = google_container_cluster.this.name, context = { cluster = google_container_cluster.this.name, user = google_container_cluster.this.name } }]
    users = [{ name = google_container_cluster.this.name, user = { exec = {
      apiVersion         = "client.authentication.k8s.io/v1beta1"
      command            = "gke-gcloud-auth-plugin"
      provideClusterInfo = true
    } } }]
  })
}
