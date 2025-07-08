variable "namespace" {
  description = "namespace"
}

resource "helm_release" "pg_operator" {
  name       = "patroni-core"
  namespace  = var.namespace
  create_namespace = true
  chart      = "../pgskipper-operator/charts/patroni-core"
  timeout    = 1200
  #values     = ["../../pgskipper-operator/charts/patroni-core/values.yaml"]
  values = [file("values.yaml")]
}
