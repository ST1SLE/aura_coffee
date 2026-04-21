"""Celery-таски, owned by core-api codebase.

Бизнес-логика живёт в `core_api.services.*`; модули здесь — тонкие обёртки,
зарегистрированные через `celery_app(include=[...])`.
"""
