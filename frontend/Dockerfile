FROM node:22-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# 本番では Django の staticfiles として配信するため、成果物だけを取り出す
FROM scratch AS dist
COPY --from=build /app/dist /dist
