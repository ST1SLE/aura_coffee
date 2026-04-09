from payment_worker.main import celery_app


@celery_app.task
def health_check() -> str:
    return "ok"
