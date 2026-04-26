# START_MODULE_CONTRACT
#   PURPOSE: Package marker for the sms-worker Celery service (M-SMS-WORKER).
#   SCOPE:   Empty package init — submodules expose Celery app, settings,
#            clients, and tasks. Importing this package does not eagerly load
#            Celery so tooling can introspect the package safely.
#   DEPENDS: M-SHARED, Celery, redis-py, httpx, cryptography
#   LINKS:   docs/development-plan.xml M-SMS-WORKER, PDD §4.3, PDD §6.4, INV-013
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   (no public exports — see sms_worker.main, sms_worker.settings,
#    sms_worker.clients, sms_worker.tasks)
# END_MODULE_MAP
