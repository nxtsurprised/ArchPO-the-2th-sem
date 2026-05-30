# ГОСТ 34 Platform: Docker Compose + Loki + Grafana

Приложение для работы с документами по ГОСТ 34. В `part1` поднимается frontend, API gateway nginx, auth/catalog/generation/workflow сервисы и инфраструктурные зависимости: PostgreSQL, MongoDB, Redis, Kafka, MinIO.

<img width="461" height="264" alt="image" src="https://github.com/user-attachments/assets/53feefc4-3432-4585-8bdf-0b0f1bf337d8" />

<img width="461" height="236" alt="image" src="https://github.com/user-attachments/assets/2bb89e1b-96ea-4e2e-89d5-7a698e11ac4c" />

Кнопка запуска ПМИ в интерфейсе сохранена как заглушка: `/api/pmi/*` возвращает stub-ответ из nginx. Тяжелый `pmi-agent` с Ollama/Playwright/ML-зависимостями не включен в этот Docker Compose вариант, чтобы стенд запускался стабильно.

В этой ветке стабильно реализована итоговая работа только с использованием docker compose. Папки platform и workflows остались из ветки ```part-3```, которая реализовывалась в рамках другого предмета. Ее под требование «За дополнительные 5 баллов можно реализовать итоговую в миникубе через манифесты. Тогда нужно будет:
прикрепить скрины неймспейсов, сервайсов и подов. Неймспейс необходимо будет назвать по маске <имя><дата>» не подгоняла, поэтому на эти папки не нужно обращать внимание.


## Запуск

Требования: Docker, Docker Compose, curl.

```bash
cd part1
bash scripts/build.sh -t v1
bash scripts/deploy.sh -t v1
```
### Описание build.sh
  - читает тег из -t coursework;
  - генерирует секреты через generate_secrets.sh;
  - запускает docker compose build;
  - собирает образы:
      - gost34-frontend:coursework
      - gost34-auth-service:coursework
      - gost34-catalog-service:coursework
      - gost34-generation-service:coursework
      - gost34-workflow-service:coursework

### Описание deploy.sh
  - читает тег из -t coursework;
  - генерирует секреты, если нужно;
  - запускает:

    docker compose up -d --remove-orphans

  - поднимает backend, frontend, nginx, базы, Redis, Kafka, MinIO, Loki,
    Prometheus, Grafana;
  - использует образы с тегом coursework;
  - печатает адреса:
      - приложение: http://localhost:8081
      - Grafana: http://localhost:3001
      - Loki: http://localhost:3100
      - Kafka UI: http://localhost:9080
      - MinIO: http://localhost:9001
### Описание stop.sh
  - читает тег из -t coursework;
  - запускает:
    docker compose down
  - останавливает контейнеры и сеть;
  - данные в volumes не удаляет.
### Описание generate_logs.sh
  Создает тестовые HTTP-запросы к приложению, чтобы появились логи для Grafana/
  Loki.
  - дергает разные endpoint’ы приложения через nginx;
  - создает успешные и ошибочные запросы;
  - эти запросы попадают в Docker logs;
  - Promtail забирает их и отправляет в Loki;
  - после этого их можно смотреть в Grafana через LogQL, например:
    {service="nginx"}
###  Описание generate_secrets.sh
  Вспомогательный скрипт для создания локальных секретов.
  - создает директорию part1/secrets;
  - генерирует JWT private/public ключи;
  - создает .env с паролями/ключами, если их еще нет;
  - нужен, чтобы auth-service и остальные сервисы могли стартовать локально.

## Адреса:

- приложение: http://localhost:8081
- Grafana: http://localhost:3001, логин/пароль `admin` / `admin`
- Loki: http://localhost:3100
- Kafka UI: http://localhost:9080
- MinIO: http://localhost:9001

Остановка:

```bash
cd part1
bash scripts/stop.sh -t v1
```

## Скрины рабочего варианта приложения
```docker compose ps```
<img width="1672" height="353" alt="image" src="https://github.com/user-attachments/assets/83e20bb5-83af-4e34-9b21-3360041bf819" />


Пользовательский интерфейс:
<img width="1800" height="1017" alt="image" src="https://github.com/user-attachments/assets/e73910df-0776-4d0f-b3e9-d2ef24654105" />
<img width="1800" height="1017" alt="image" src="https://github.com/user-attachments/assets/2fba56f9-48ef-44e8-abf2-974c7f24a311" />
<img width="1800" height="1017" alt="image" src="https://github.com/user-attachments/assets/dd664173-ede2-41b1-9d76-008cfd067f86" />
<img width="1800" height="1017" alt="image" src="https://github.com/user-attachments/assets/61433cc2-cc2b-4cf8-997c-d00ebf7e9305" />
<img width="1800" height="1017" alt="image" src="https://github.com/user-attachments/assets/2388201e-b149-4b3a-98ec-64edaaf72375" />
<img width="1800" height="1017" alt="image" src="https://github.com/user-attachments/assets/5c798ae3-7fb0-428c-87c4-c050fe5462a6" />




## Логи в Grafana
### Grafana интерфейс
<img width="1800" height="1017" alt="image" src="https://github.com/user-attachments/assets/cee2d7cb-0f60-441c-96d4-d593f26c7b26" />

<img width="1800" height="1017" alt="image" src="https://github.com/user-attachments/assets/a8c47853-70ce-4e78-9edf-bb656700739d" />

<img width="1800" height="1017" alt="image" src="https://github.com/user-attachments/assets/923d7a70-b953-4880-a4cd-1d5c4f9f6004" />


В compose уже поднимаются `loki`, `promtail` и `grafana`. Promtail читает Docker-логи контейнеров проекта `part1` и отправляет их в Loki. В Grafana datasource `Loki` добавлен автоматически.

### Проверка логирования
Чтобы быстро создать логи:

```bash
cd part1
bash scripts/generate_logs.sh
```

В Grafana открыть `Explore`, выбрать datasource `Loki` и выполнить запросы:

```logql
{service="nginx"}
{service="auth-service"}
{service="catalog-service"}
{container=~"part1-.*"}
```
<img width="1800" height="1017" alt="image" src="https://github.com/user-attachments/assets/2da177c6-b702-4299-8fc8-0ba324d6b32d" />


## Multistage

Multistage-сборка описана в Dockerfile для frontend и Python-сервисов с зависимостями: `auth-service`, `catalog-service`, `generation-service`, `workflow-service`.
