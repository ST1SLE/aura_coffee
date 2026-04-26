# START_MODULE_CONTRACT
#   PURPOSE: Package marker for FastAPI routers under M-CORE-API. Each submodule
#            owns one APIRouter — see services/core-api/src/core_api/main.py
#            for include_router wiring. Empty by design — no re-exports.
#   SCOPE:   No public symbols; routers are imported by FQN
#            (core_api.routers.<name>.router).
#   DEPENDS: none directly; submodules depend on M-SHARED, M-DATABASE,
#            core_api.services.*, core_api.deps.*.
#   LINKS:   docs/development-plan.xml M-CORE-API,
#            services/core-api/AGENTS.md.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   (no public symbols — submodules expose `router` attributes)
# END_MODULE_MAP
