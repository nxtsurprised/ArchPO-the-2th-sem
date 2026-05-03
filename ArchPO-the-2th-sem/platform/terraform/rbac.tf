resource "kubernetes_role_v1" "app_config_reader" {
  metadata {
    name      = "app-config-reader"
    namespace = kubernetes_namespace_v1.base["app"].metadata[0].name
  }

  rule {
    api_groups     = [""]
    resources      = ["configmaps"]
    resource_names = [kubernetes_config_map_v1.app_config.metadata[0].name]
    verbs          = ["get", "list", "watch"]
  }
}

resource "kubernetes_role_binding_v1" "app_config_readers" {
  metadata {
    name      = "app-config-readers"
    namespace = kubernetes_namespace_v1.base["app"].metadata[0].name
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.app_config_reader.metadata[0].name
  }

  dynamic "subject" {
    for_each = kubernetes_service_account_v1.app

    content {
      kind      = "ServiceAccount"
      name      = subject.value.metadata[0].name
      namespace = kubernetes_namespace_v1.base["app"].metadata[0].name
    }
  }
}
