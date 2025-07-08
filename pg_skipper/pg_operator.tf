resource "helm_release" "pg_operator" {
  name       = "patroni-core"
  namespace  = "pg-test-1"
  create_namespace = true
  chart      = "../pgskipper-operator/charts/patroni-core"
  timeout    = 1200
  #values     = ["../../pgskipper-operator/charts/patroni-core/values.yaml"]
  values = [file("values.yaml")]
}
