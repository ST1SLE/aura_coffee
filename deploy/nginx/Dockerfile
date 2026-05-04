FROM node:22-alpine AS customer-build

WORKDIR /app/web/customer
COPY web/customer/package*.json ./
RUN npm ci
COPY web/shared-config /app/web/shared-config
COPY web/customer ./
RUN npm run build

FROM node:22-alpine AS admin-build

WORKDIR /app/web/admin
COPY web/admin/package*.json ./
RUN npm ci
COPY web/shared-config /app/web/shared-config
COPY web/admin ./
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/nginx/nginx.production.conf /etc/nginx/conf.d/default.conf
COPY --from=customer-build /app/web/customer/dist /usr/share/nginx/html
COPY --from=admin-build /app/web/admin/dist /usr/share/nginx/html/admin

RUN mkdir -p /srv/aura-coffee/media/menu
