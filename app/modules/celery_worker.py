from celery import Celery
import os

def make_celery(app=None):
    """Initialize Celery with Redis as the broker."""
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    celery = Celery("arcadescore", broker=redis_url, backend=redis_url)
    
    if app:
        celery.conf.update(app.config)
    
    return celery

celery = make_celery()
