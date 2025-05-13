import redis
from typing import Optional

redis_client = redis.StrictRedis(host="localhost", port=6379, db=0)

def cache_order(phone: str, order_id: str):
    """
    Cache the order ID for a given phone number.
    """
    redis_client.rpush(phone, order_id)

def get_latest_order(phone: str) -> Optional[str]:
    """
    Retrieve the latest order ID for a given phone number.
    """
    orders = redis_client.lrange(phone, 0, -1)
    return orders[-1].decode("utf-8") if orders else None