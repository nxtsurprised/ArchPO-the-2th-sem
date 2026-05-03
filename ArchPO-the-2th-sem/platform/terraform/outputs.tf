output "namespace_names" {
  description = "Созданные базовые namespace."
  value       = { for key, namespace in kubernetes_namespace_v1.base : key => namespace.metadata[0].name }
}

output "app_service_account_names" {
  description = "ServiceAccount для сервисов приложения в namespace app."
  value       = [for service_account in kubernetes_service_account_v1.app : service_account.metadata[0].name]
}
