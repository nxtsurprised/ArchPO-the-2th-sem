# Block 4: Сравнение Observability Стеков

## Итоговое Решение

Для Kubernetes-части выбран стек:

- Metrics: Prometheus.
- Logs: Loki + Promtail.
- Visualization: Grafana.
- Alerts: Alertmanager.
- Traces: OpenTelemetry Collector + Tempo.

Аргументы выбора:

- этот стек продолжает направление, уже реализованное в `part1/` через Docker Compose: Prometheus, Grafana, Loki, Promtail и Alertmanager;
- Prometheus подходит для существующих `/metrics` endpoints и учебного масштаба;
- Grafana может показывать metrics, logs и traces в одном UI;
- Loki легче ELK для локальной агрегации логов в k3d/k3s;
- Tempo лучше вписывается в Grafana-экосистему, чем отдельный tracing UI;
- OpenTelemetry Collector сохраняет трассировку vendor-neutral;
- VictoriaMetrics и VictoriaLogs являются хорошими альтернативами для большего масштаба, но не нужны для локального demo;
- ELK и SigNoz тяжелее, чем требуется на этом этапе.

## Сравнение По Сигналам

| Сигнал | Вариант | Плюсы | Минусы | Локальный footprint |
| --- | --- | --- | --- | --- |
| Logs | Loki | Легкий, хорошо интегрируется с Grafana, не индексирует полный текст логов | Требует аккуратных labels, не заменяет ELK-style полнотекстовый поиск | Низкий |
| Logs | VictoriaLogs | Быстрая запись, хорош для больших объемов логов | Меньше связан с уже используемым стеком проекта | Низкий-средний |
| Logs | Elasticsearch + Logstash + Kibana | Сильный полнотекстовый поиск, зрелая экосистема | Тяжелый стек, много потребляет памяти, сложнее эксплуатация | Высокий |
| Logs | SigNoz | Единая платформа для logs, metrics и traces | Обычно требует ClickHouse и больше компонентов | Средний-высокий |
| Metrics | Prometheus | Kubernetes-стандарт, простая scrape-модель, уже используется в `part1/` | Встроенное long-term storage ограничено | Низкий |
| Metrics | VictoriaMetrics | Эффективное хранение, хорошая производительность | Cluster mode сложнее для локального учебного стенда | Низкий-средний |
| Metrics | InfluxDB | Хорош для time-series и IoT-style workloads | Менее стандартен для Kubernetes service discovery | Средний |
| Traces | Jaeger | Зрелый tracing UI, широко известен | Отдельный UI и варианты storage увеличивают operational surface | Средний |
| Traces | Uptrace | OpenTelemetry-first, удобный UI | Добавляет отдельный продукт для локального coursework setup | Средний |
| Traces | Tempo | Хорошо работает с Grafana, может хранить traces без тяжелого индекса | UI в основном через Grafana, требуется instrumentation | Низкий |

## Сравнение Стеков

| Стек | Плюсы | Минусы | Подходит Для local k3d/k3s |
| --- | --- | --- | --- |
| Prometheus + Loki + Grafana + Tempo | Легкий, продолжает `part1`, один Grafana UI для всех сигналов, мало новых концепций | Нет long-term storage, traces пустые без instrumentation | Да |
| VictoriaMetrics Cluster + VictoriaLogs + Grafana + Jaeger | Хорош для большего объема данных, эффективное хранение | Cluster mode и Jaeger утяжеляют локальную установку | Частично, но избыточно |
| VictoriaMetrics + OpenTelemetry Collector + ClickHouse + Grafana | Гибкий OpenTelemetry pipeline, ClickHouse хорошо масштабируется | ClickHouse добавляет отдельную БД и resource footprint | Не для этого этапа |
| SigNoz all-in-one | Быстрый старт как единая observability-платформа | Тяжелее выбранного стека, слабее связан с существующим Docker Compose setup | Возможен, но не выбран |

## Почему Это Подходит Проекту

`part1/` уже содержит Docker Compose observability: Prometheus, Grafana, Loki, Promtail и Alertmanager. Block 4 не переписывает этот слой и не меняет код сервисов. Он добавляет отдельный Kubernetes-вариант под `platform/observability`, чтобы observability можно было проверить в локальном k3d/k3s-кластере.

Выбранный стек покрывает базовые сигналы:

- metrics Kubernetes, Istio и приложений из Pod с `prometheus.io/scrape=true`;
- Kubernetes Pod logs через Promtail и Loki;
- Prometheus alerts через Alertmanager без реальных внешних секретов;
- traces через OpenTelemetry Collector и Tempo, когда приложения или Istio будут настроены отправлять spans.

## Что Отложено

- ELK не разворачивается: он слишком тяжелый для локального demo и не нужен для coursework-scale логов.
- VictoriaMetrics Cluster и VictoriaLogs не разворачиваются: это хорошие варианты для роста, но сейчас они добавляют эксплуатационную сложность.
- SigNoz и ClickHouse не разворачиваются: они полезны для all-in-one observability, но добавляют лишние компоненты для этого блока.
- Long-term storage не настраивается: все хранилища используют `emptyDir`, потому что цель - воспроизводимая локальная проверка.
- Полный AI monitoring не реализован: текущий уровень ограничен техническими метриками PMI Agent и документацией будущих LLM spans и quality dashboards.
