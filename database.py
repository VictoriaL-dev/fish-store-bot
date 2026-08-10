import logging
import asyncio

import redis.asyncio as aioredis
from redis.exceptions import RedisError, ConnectionError, TimeoutError

logger = logging.getLogger("bot.db")


async def get_db_connection(host, port, password):
    """Creates an asynchronous connection pool and returns a Redis client.

    Args:
        host (str): The hostname or IP address of the Redis server.
        port (int): The port number the Redis server is listening on.
        password (str): The password required for Redis authentication.

    Returns:
        redis.asyncio.Redis: Returns a configured Redis client.
    """
    redis_pool = aioredis.ConnectionPool(
        host=host,
        port=port,
        password=password,
        protocol=3,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        max_connections=20
    )
    redis_db = aioredis.Redis(connection_pool=redis_pool)

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            await redis_db.ping()
            logger.info("Successfully connected to Redis.")
            break
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis connection attempt {attempt}/{max_retries} failed: {e}")
            if attempt == max_retries:
                logger.critical("Could not establish connection to Redis. Shutting down...")
                await redis_pool.disconnect()
                raise e
            await asyncio.sleep(2)
    return redis_db


async def close_db_connection(redis_db):
    """Safely closes the Redis client and its underlying connection pool.

    Args:
        redis_db (redis.asyncio.Redis): The active Redis client instance to close.

    Returns:
        None: This coroutine does not return a value.
    """
    if redis_db:
        try:
            await redis_db.aclose(close_connection_pool=True)
            logger.info("Redis connection and pool successfully closed.")
        except RedisError as e:
            logger.exception(f"Error occurred while closing Redis connection: {e}")
