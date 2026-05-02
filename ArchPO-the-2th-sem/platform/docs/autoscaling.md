# Подход К Автомасштабированию

Этот блок локально проверяет автомасштабирование подов и документирует дизайн автомасштабирования worker-нод.

## Две Разные Задачи Масштабирования

В Kubernetes есть две отдельные задачи автомасштабирования:

- масштабирование подов меняет количество replica подов;
- масштабирование нод меняет количество worker-нод.

Эти механизмы связаны, но решают разные проблемы.

## HPA: Локальное Масштабирование Подов

Horizontal Pod Autoscaler наблюдает за метриками workload и изменяет количество replica.

HPA-демо находится в `platform/autoscaling/hpa/`:

- `demo-app.yaml` создает Deployment и Service с приложением, которое можно нагрузить по CPU.
- `hpa.yaml` создает HPA, нацеленный на этот Deployment.
- `load-generator.yaml` создает pod, который постоянно вызывает demo Service.

Цель HPA настроена на CPU utilization. Когда load generator создает достаточно трафика, CPU usage растет, и HPA увеличивает количество replica у Deployment.

## Metrics Server

HPA нужны метрики. В этой конфигурации metrics-server предоставляет CPU и memory metrics через Kubernetes metrics API.

Для локальных k3d/k3s-кластеров metrics-server обычно требует `--kubelet-insecure-tls`, потому что kubelet certificates в локальной среде self-signed.

Это допустимо для локальной проверки. Это не production-рекомендация по безопасности.

## Cluster Autoscaler: Дизайн Масштабирования Нод

Cluster Autoscaler выбран как дизайн автомасштабирования worker-нод для этого проекта.

Cluster Autoscaler следит за подами, которые не могут быть запланированы из-за нехватки capacity в кластере. Когда он находит такие поды, он просит infrastructure provider добавить ноды. Также он может удалять недоиспользуемые ноды, если их можно безопасно drain-ить.

## Почему Масштабирование Нод Не Запускается Локально

В k3d worker-ноды являются Docker-контейнерами. Обычный локальный кластер не предоставляет cloud API или Cluster API provider, которые нужны Cluster Autoscaler для создания и удаления машин.

Реальное автомасштабирование worker-нод требует один из backend:

- интеграция с cloud provider;
- Cluster API с infrastructure provider;
- provider-specific реализация, которая умеет управлять node groups.

У Karpenter есть такое же требование. Он полезен в реальной инфраструктуре, но ему тоже нужен provider, способный provision-ить машины.

## Решение В Проекте

Для Block 1:

- HPA реализован и проверяется локально.
- Cluster Autoscaler документируется как дизайн масштабирования worker-нод.
- `platform/autoscaling/cluster-autoscaler/values.example.yaml` содержит только placeholders.
- Реальные учетные данные и fake cloud configuration не добавляются.
