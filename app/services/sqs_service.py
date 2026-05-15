import json

from app.core.aws import sqs_client
from app.core.config import settings


def select_queue_url(plan: str) -> str:
    if plan == "paid":
        if not settings.paid_queue_url:
            raise RuntimeError("PAID_QUEUE_URL is not configured")
        return settings.paid_queue_url

    if not settings.free_queue_url:
        raise RuntimeError("FREE_QUEUE_URL is not configured")
    return settings.free_queue_url


def send_inference_message(message: dict) -> dict:
    queue_url = select_queue_url(message.get("plan", "free"))

    return sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message, ensure_ascii=False),
    )
