"""
    Helper file to provide a redis client to the configured
    redis-server pointed to by environment variables.

    Usage: From a python repl - `from redis_client import *`

    You can then use redis_client to inspect data stored
    in redis.
"""
import os
import redis
from dotenv import load_dotenv
from ec601_proj2.workers import Queues

load_dotenv()

REDIS_SERVER_HOST = os.getenv("REDIS_SERVER_HOST")
REDIS_SERVER_PORT = int(os.getenv("REDIS_SERVER_PORT"))
REDIS_SERVER_DB = int(os.getenv("REDIS_SERVER_DB"))
redis_client = redis.Redis(REDIS_SERVER_HOST,
                           REDIS_SERVER_PORT,
                           REDIS_SERVER_DB)
