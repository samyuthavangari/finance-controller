FROM node:22-alpine AS build
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend ./
ARG VITE_API_URL=http://localhost:8000
ARG VITE_API_TOKEN=demo-token
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_API_TOKEN=$VITE_API_TOKEN
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /ui/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
