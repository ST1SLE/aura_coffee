## Context

**Affected modules**: [sms-worker]

The sms-worker has a namespace collision: `sms_worker/tasks.py` and `sms_worker/tasks/` (a package) coexist. Python resolves `import sms_worker.tasks` to the package (`tasks/__init__.py`), permanently shadowing the file `tasks.py`. The `health_check` task defined in `tasks.py` is unreachable. The `autodiscover_tasks(["sms_worker", "sms_worker.tasks"])` call in `main.py` cannot find tasks in the shadowed file.

Current file layout:
```
sms_worker/
├── main.py            # celery_app + autodiscover_tasks
├── tasks.py           # health_check (SHADOWED — unreachable)
└── tasks/
    ├── __init__.py    # empty
    └── otp.py         # send_otp_sms
```

## Goals / Non-Goals

**Goals:**
- Eliminate the `tasks.py` / `tasks/` naming conflict so all Celery tasks are discoverable
- Preserve the `tasks/` package structure for organizing task modules
- Keep the `health_check` task accessible

**Non-Goals:**
- Changing task signatures, retry policies, or business logic
- Refactoring payment-worker (no conflict there)
- Modifying Docker or compose configuration

## Decisions

### Decision 1: Delete `tasks.py`, move `health_check` into `tasks/__init__.py`

**Choice**: Remove `tasks.py` entirely. Move the `health_check` task into `tasks/__init__.py`.

**Alternatives considered**:
- *Move health_check to `tasks/health.py`*: Creates an extra module for a single trivial function. Unnecessarily changes the import path to `sms_worker.tasks.health.health_check`.
- *Delete `tasks/` and keep `tasks.py`*: Would require moving `otp.py` contents into a single file, losing the package structure needed as more task types are added (order notifications, etc.).

**Rationale**: Placing `health_check` in `tasks/__init__.py` keeps the import path as `sms_worker.tasks.health_check` — closest to the original intent. The package remains extensible for future task modules.

### Decision 2: Simplify `autodiscover_tasks` to use package scanning

**Choice**: Change `celery_app.autodiscover_tasks(["sms_worker", "sms_worker.tasks"])` to `celery_app.autodiscover_tasks(["sms_worker.tasks"])`.

**Alternatives considered**:
- *Keep both entries*: Redundant now that `tasks.py` is removed. The `sms_worker` entry would scan for a `tasks` submodule which IS the `tasks/` package — same result but confusing.
- *Use `include` in Celery config*: Explicit but brittle — requires updating config every time a task module is added.

**Rationale**: `autodiscover_tasks(["sms_worker.tasks"])` scans all modules inside the `tasks/` package. Tasks in `__init__.py` and `otp.py` are both discovered automatically. New modules added to `tasks/` SHALL be discovered without config changes.

## Risks / Trade-offs

- **[Risk] Import path change for health_check** → Any code calling `sms_worker.tasks.health_check` by its old import still works because the task is now in `tasks/__init__.py`, which IS `sms_worker.tasks`. Mitigation: verify with a test.
- **[Risk] Celery task name changes** → Celery auto-generates task names from the module path. `sms_worker.tasks.health_check` remains the same since `__init__.py` maps to `sms_worker.tasks`. No risk.
- **[Risk] `send_otp_sms` discovery regression** → `otp.py` is already inside `tasks/` and SHALL continue to be discovered. Mitigation: run existing tests after the change.
