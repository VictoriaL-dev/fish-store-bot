import redis


def get_database_connection(host: str, port: int, password: str) -> redis.Redis:
    """Returns a connection to the Redis database. Raises error if connection fails."""
    redis_db = redis.Redis(
        host=host,
        port=port,
        password=password,
        protocol=3,
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_db.ping()
    return redis_db
