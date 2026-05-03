resource "kubernetes_namespace_v1" "base" {
  for_each = local.namespaces

  metadata {
    name = each.value

    labels = {
      "app.kubernetes.io/part-of"    = "archpo-platform"
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
}
