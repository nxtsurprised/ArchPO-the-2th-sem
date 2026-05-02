FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Финальный образ: просто копирует dist в volume при запуске
FROM alpine:3.19
COPY --from=builder /app/dist /static
CMD ["sh", "-c", "cp -r /static/. /output/ && echo 'Frontend files ready'"]
