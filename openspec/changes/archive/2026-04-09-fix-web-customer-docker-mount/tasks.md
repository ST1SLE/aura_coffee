## 1. Fix Docker Compose volume mounts

- [x] 1.1 [web-customer] Add `./web/shared-config:/shared-config:ro` volume mount to `web-customer` service in `docker-compose.yml`
- [x] 1.2 [web-admin] Add `./web/shared-config:/shared-config:ro` volume mount to `web-admin` service in `docker-compose.yml`

## 2. Verify

- [x] 2.1 [web-customer] Restart containers and confirm `web-customer` Vite dev server compiles CSS without errors
- [x] 2.2 [web-admin] Confirm `web-admin` Vite dev server compiles CSS without errors
