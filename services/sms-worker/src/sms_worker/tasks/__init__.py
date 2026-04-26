# START_MODULE_CONTRACT
#   PURPOSE: Celery task package — exposes a liveness probe and re-exports
#            OTP/notification tasks so Celery autodiscovery wires them onto
#            the "sms" queue.
#   SCOPE:   Defines the `health_check` task and re-exports `send_otp_sms`
#            from sms_worker.tasks.otp. Notification task is autodiscovered
#            from sms_worker.tasks.notification.
#   DEPENDS: sms_worker.main (celery_app), sms_worker.tasks.otp
#   LINKS:   docs/development-plan.xml M-SMS-WORKER, PDD §6.4, PDD §7.8
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   health_check  - Celery liveness task returning "ok"
#   send_otp_sms  - re-export from sms_worker.tasks.otp (OTP delivery task)
# END_MODULE_MAP

from sms_worker.main import celery_app
from sms_worker.tasks.otp import send_otp_sms  # noqa: F401


# START_CONTRACT: health_check
#   PURPOSE: Trivial Celery task used by deploy/CI smoke-tests to confirm the
#            worker is consuming from the "sms" queue.
#   INPUTS:  (none)
#   OUTPUTS: str — literal "ok"
#   SIDE_EFFECTS: none (no I/O, no DB, no network)
#   LINKS:   docs/development-plan.xml M-SMS-WORKER (operational liveness)
# END_CONTRACT: health_check
@celery_app.task
def health_check() -> str:
    return "ok"
