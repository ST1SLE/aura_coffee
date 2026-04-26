# START_MODULE_CONTRACT
#   PURPOSE: Construct and configure the Celery application instance for the
#            SMS worker — single broker, single "sms" queue, autodiscovery of
#            task modules.
#   SCOPE:   Wires Celery to Redis (broker), declares the "sms" queue, and
#            triggers autodiscovery of sms_worker.tasks. No business logic.
#   DEPENDS: M-SHARED, Celery, kombu, sms_worker.settings
#   LINKS:   docs/development-plan.xml M-SMS-WORKER, PDD §4.3, PDD §7.8
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   celery_app - configured Celery application bound to the "sms" queue
# END_MODULE_MAP

from celery import Celery
from kombu import Queue

from sms_worker.settings import settings

celery_app = Celery(
    "sms_worker",
    broker=settings.redis_url,
)

celery_app.conf.task_queues = [Queue("sms")]
celery_app.conf.task_default_queue = "sms"

celery_app.autodiscover_tasks(["sms_worker.tasks"])
