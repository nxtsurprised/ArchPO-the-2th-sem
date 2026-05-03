locals {
  namespaces = {
    app           = "app"
    infra         = "infra"
    argocd        = "argocd"
    kafka         = "kafka"
    databases     = "databases"
    observability = "observability"
  }

  app_service_accounts = [
    "auth-service",
    "catalog-service",
    "generation-service",
    "workflow-service",
    "pmi-agent",
    "frontend",
  ]

  app_config = {
    KAFKA_BOOTSTRAP_SERVERS = "archpo-kafka-kafka-bootstrap.kafka.svc.cluster.local:9092"
    REDIS_URL               = "redis://redis.databases.svc.cluster.local:6379/0"
    MINIO_ENDPOINT          = "http://minio.databases.svc.cluster.local:9000"
    OBSERVABILITY_ENABLED   = "true"
  }
}
