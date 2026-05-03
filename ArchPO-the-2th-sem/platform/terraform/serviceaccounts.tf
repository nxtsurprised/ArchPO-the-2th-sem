resource "kubernetes_service_account_v1" "app" {
  for_each = toset(local.app_service_accounts)

  metadata {
    name      = each.value
    namespace = kubernetes_namespace_v1.base["app"].metadata[0].name

    labels = {
      "app.kubernetes.io/name"       = each.value
      "app.kubernetes.io/part-of"    = "archpo-platform"
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
}
