# START_MODULE_CONTRACT
#   PURPOSE: Package marker for SMS transport clients (live SMS.ru and dev log).
#   SCOPE:   Empty package init — concrete transports live in sibling modules
#            (smsru.py for production, log.py for local development).
#   DEPENDS: M-SHARED, httpx (smsru), stdlib logging (log)
#   LINKS:   docs/development-plan.xml M-SMS-WORKER, PDD §7.8, PDD §8.2,
#            INV-013, INV-015
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   (no public exports — see sms_worker.clients.smsru, sms_worker.clients.log)
# END_MODULE_MAP
