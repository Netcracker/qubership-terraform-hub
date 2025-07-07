resource "helm_release" "pg_operator" {
  name       = "patroni-core"
  namespace  = "pg_test"
  chart      = "../pgskipper-operator/charts/patroni-core"
  timeout    = 1200
  values     = ["../pgskipper-operator/charts/patroni-core/values.yaml"]
}
