variable "kubeconfig_path" {
  description = "Путь к kubeconfig. По умолчанию используется стандартный kubeconfig текущего пользователя."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Имя Kubernetes context для локального k3d/k3s-кластера."
  type        = string
  default     = "k3d-archpo-local"
}

variable "app_shared_secrets" {
  description = "Демо-секреты общего назначения для namespace app."
  type        = map(string)
  sensitive   = true
  default = {
    INTERNAL_API_TOKEN = "demo-internal-token-change-me"
    ENCRYPTION_KEY     = "demo-local-encryption-key-change-me"
  }
}

variable "jwt_secrets" {
  description = "Демо-секреты JWT для namespace app."
  type        = map(string)
  sensitive   = true
  default = {
    JWT_SECRET_KEY = "demo-jwt-secret-change-me"
    JWT_ALGORITHM  = "HS256"
  }
}

variable "postgres_secret" {
  description = "Демо-секреты PostgreSQL для namespace databases."
  type        = map(string)
  sensitive   = true
  default = {
    POSTGRES_USER     = "archpo"
    POSTGRES_PASSWORD = "demo-postgres-password"
    POSTGRES_DB       = "archpo"
  }
}

variable "mongo_secret" {
  description = "Демо-секреты MongoDB для namespace databases."
  type        = map(string)
  sensitive   = true
  default = {
    MONGO_INITDB_ROOT_USERNAME = "archpo"
    MONGO_INITDB_ROOT_PASSWORD = "demo-mongo-password"
  }
}

variable "redis_secret" {
  description = "Демо-секреты Redis для namespace databases."
  type        = map(string)
  sensitive   = true
  default = {
    REDIS_PASSWORD = "demo-redis-password"
  }
}

variable "minio_secret" {
  description = "Демо-секреты MinIO для namespace databases."
  type        = map(string)
  sensitive   = true
  default = {
    MINIO_ROOT_USER     = "archpo"
    MINIO_ROOT_PASSWORD = "demo-minio-password"
  }
}
