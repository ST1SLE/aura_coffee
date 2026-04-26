# START_MODULE_CONTRACT
#   PURPOSE: Package marker for database.seeds — namespace for one-shot seed
#            scripts (initial admin, shop settings singleton, manual-QA fixtures).
#   SCOPE:   Empty by design; import side-effects are kept out of __init__ so
#            seeds run only when invoked explicitly via `python -m database.seeds.<name>`.
#   DEPENDS: none (pure package marker)
#   LINKS:   docs/development-plan.xml M-DATABASE, database/AGENTS.md
#            "Schema-only migrations" / "Running the initial admin seed"
#   ROLE:    CONFIG
#   MAP_MODE: NONE
# END_MODULE_CONTRACT
