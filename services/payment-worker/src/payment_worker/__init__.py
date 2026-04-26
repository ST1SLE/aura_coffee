# START_MODULE_CONTRACT
#   PURPOSE: Marker module for the payment_worker Python package; intentionally
#            empty so importers (Celery autodiscover, tests, sibling services)
#            see a regular package without side-effects.
#   SCOPE:   Package init only. No public exports — submodules expose Celery
#            tasks (tasks.py, yukassa_fake.py), the FastAPI webhook app
#            (webhook.py), and the YuKassa HTTP clients (yukassa_client.py,
#            yukassa_fake.py).
#   DEPENDS: none
#   LINKS:   docs/development-plan.xml M-PAYMENT-WORKER, PDD §4.2, §6.2
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   (no exports — package marker only)
# END_MODULE_MAP
