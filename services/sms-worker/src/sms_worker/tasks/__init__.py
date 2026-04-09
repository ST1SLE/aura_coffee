from sms_worker.main import celery_app
from sms_worker.tasks.otp import send_otp_sms  # noqa: F401


@celery_app.task
def health_check() -> str:
    return "ok"
