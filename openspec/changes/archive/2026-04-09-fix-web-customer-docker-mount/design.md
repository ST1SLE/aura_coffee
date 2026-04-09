## Context

**Affected modules:** [web-customer], [web-admin]

Both `web-customer` and `web-admin` containers use `node:22-alpine` with a volume mount of their respective `web/<app>` directory to `/app`. Both `tailwind.config.ts` files reference `../shared-config/tailwind-preset` via `require()`. This relative path resolves to `/shared-config/tailwind-preset` inside the container — a path that does not exist because only the app directory is mounted.

Current docker-compose mounts:
```yaml
web-customer:
  volumes:
    - ./web/customer:/app           # only customer code
    - customer_node_modules:/app/node_modules

web-admin:
  volumes:
    - ./web/admin:/app              # only admin code
    - admin_node_modules:/app/node_modules
```

## Goals / Non-Goals

**Goals:**
- CSS compilation SHALL work inside both `web-customer` and `web-admin` containers
- `shared-config/tailwind-preset` SHALL be accessible at the expected relative path

**Non-Goals:**
- Changing Tailwind config import paths in application code
- Dockerizing frontends with multi-stage builds (future concern)
- Fixing unrelated container issues (nginx, sms-worker)

## Decisions

### Decision 1: Add a dedicated volume mount for shared-config

**Choice:** Mount `./web/shared-config` to `/shared-config` in both frontend containers.

**Rationale:** The `require('../shared-config/tailwind-preset')` from `/app/tailwind.config.ts` resolves to `/shared-config/tailwind-preset`. Mounting `./web/shared-config` → `/shared-config` satisfies this path exactly.

**Alternative considered:** Mount entire `./web` directory and change `working_dir` to `/web/customer`. Rejected because it changes the node_modules path assumption and may break the named volume `customer_node_modules:/app/node_modules`.

**Alternative considered:** Copy `shared-config` into each app directory. Rejected — duplicates code and drifts.

## Risks / Trade-offs

- **[Risk]** Future shared modules under `web/` will need similar mounts → **Mitigation:** If this pattern repeats, switch to mounting `./web` wholesale. For now, one extra mount is acceptable.
- **[Risk]** Read-only vs read-write mount → **Mitigation:** Mount as read-only (`:ro`) since frontends only read the preset, never write to it.
