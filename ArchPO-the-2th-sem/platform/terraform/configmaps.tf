resource "kubernetes_config_map_v1" "app_config" {
  metadata {
    name      = "app-config"
    namespace = kubernetes_namespace_v1.base["app"].metadata[0].name
  }

  data = local.app_config
}
