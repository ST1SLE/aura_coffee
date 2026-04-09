## ADDED Requirements

### Requirement: Frontend containers MUST mount shared-config
Both `web-customer` and `web-admin` Docker Compose services SHALL mount `./web/shared-config` so that Tailwind CSS preset is resolvable at build time.

#### Scenario: web-customer CSS compilation succeeds
- **WHEN** `docker compose up web-customer` starts
- **THEN** Vite dev server compiles `index.css` without `Cannot find module '../shared-config/tailwind-preset'` error

#### Scenario: web-admin CSS compilation succeeds
- **WHEN** `docker compose up web-admin` starts
- **THEN** Vite dev server compiles CSS without shared-config module errors
