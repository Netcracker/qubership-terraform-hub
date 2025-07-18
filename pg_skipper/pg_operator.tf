variable "PG_INSTALL_NAMESPACE" {
  type        = string
}

resource "helm_release" "pg_operator" {
  name       = "patroni-core"
  create_namespace = true
  namespace = var.PG_INSTALL_NAMESPACE
  chart      = "../pgskipper-operator/charts/patroni-core"
  timeout    = 60
  #values     = ["../../pgskipper-operator/charts/patroni-core/values.yaml"]
  values = [file("values.yaml")]
}
