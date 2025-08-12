variable "TF_VAR_EKS_NEW_CLUSTERNAME" {
  type        = string
}

resource "null_resource" "delete_storage_class" {
  provisioner "local-exec" {
    command = "kubectl delete storageclass gp2"
  }
}

resource "kubernetes_storage_class" "aws-ebs-csi-gp2-storage-class" {
  depends_on = [null_resource.delete_storage_class]
  metadata {
    name = "gp2"
    annotations = {
      "storageclass.kubernetes.io/is-default-class" = "true"
    }
  }
  storage_provisioner    = "kubernetes.io/aws-ebs"
  reclaim_policy         = "Delete"
  allow_volume_expansion = true
  volume_binding_mode    = "WaitForFirstConsumer"
  parameters = {
    type      = "gp2"
    fsType    = "ext4"
    tagSpecification_1 = "cost-usage=${var.TF_VAR_EKS_NEW_CLUSTERNAME}"
  }
}