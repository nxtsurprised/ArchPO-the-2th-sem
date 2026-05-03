resource "kubernetes_secret_v1" "app_shared" {
  metadata {
    name      = "app-shared-secrets"
    namespace = kubernetes_namespace_v1.base["app"].metadata[0].name
  }

  type = "Opaque"
  data = var.app_shared_secrets
}

resource "kubernetes_secret_v1" "jwt" {
  metadata {
    name      = "jwt-secrets"
    namespace = kubernetes_namespace_v1.base["app"].metadata[0].name
  }

  type = "Opaque"
  data = var.jwt_secrets
}

resource "kubernetes_secret_v1" "postgres" {
  metadata {
    name      = "postgres-secret"
    namespace = kubernetes_namespace_v1.base["databases"].metadata[0].name
  }

  type = "Opaque"
  data = var.postgres_secret
}

resource "kubernetes_secret_v1" "mongo" {
  metadata {
    name      = "mongo-secret"
    namespace = kubernetes_namespace_v1.base["databases"].metadata[0].name
  }

  type = "Opaque"
  data = var.mongo_secret
}

resource "kubernetes_secret_v1" "redis" {
  metadata {
    name      = "redis-secret"
    namespace = kubernetes_namespace_v1.base["databases"].metadata[0].name
  }

  type = "Opaque"
  data = var.redis_secret
}

resource "kubernetes_secret_v1" "minio" {
  metadata {
    name      = "minio-secret"
    namespace = kubernetes_namespace_v1.base["databases"].metadata[0].name
  }

  type = "Opaque"
  data = var.minio_secret
}
