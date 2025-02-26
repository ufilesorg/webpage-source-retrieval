import asyncio
import logging

from fastapi_mongo_base.core import db
from redis.asyncio.client import Redis
from singleton import Singleton

redis_sync, redis = db.init_redis()


class RedisSSHHandler(metaclass=Singleton):
    # REDIS_HOST = os.getenv("LOCAL_BIND_HOST")
    # REDIS_PORT = int(os.getenv("LOCAL_BIND_PORT"))

    # SSH_HOST = os.getenv("SSH_HOST")
    # SSH_PORT = int(os.getenv("SSH_PORT"))
    # SSH_USER = os.getenv("SSH_USER")
    # SSH_PASSWORD = os.getenv("SSH_PASSWORD")

    # REMOTE_REDIS_HOST = os.getenv("REMOTE_REDIS_HOST")
    # REMOTE_REDIS_PORT = int(os.getenv("REMOTE_REDIS_PORT"))

    def __init__(self, use_ssh: bool = False):
        self.use_ssh = use_ssh
        self.redis_client = None  # Initialize as None

    async def initialize(self) -> Redis:

        if self.redis_client:
            return self.redis_client

        if self.use_ssh:
            await self.start_ssh_tunnel()

        self.redis_sync, self.redis_client = db.init_redis()

        # self.redis_client = Redis(host=self.REDIS_HOST, port=self.REDIS_PORT, db=1)
        return self.redis_client

    async def start_ssh_tunnel(self):
        import asyncssh

        try:
            await asyncio.sleep(2)
            tunnel = await asyncssh.connect(
                host=self.SSH_HOST,
                port=self.SSH_PORT,
                username=self.SSH_USER,
                password=self.SSH_PASSWORD,
                known_hosts=None,
            )
            listener = await tunnel.forward_local_port(
                self.REDIS_HOST,
                self.REDIS_PORT,
                self.REMOTE_REDIS_HOST,
                self.REMOTE_REDIS_PORT,
            )
            logging.info("SSH tunnel established successfully.")
            return listener
        except Exception as e:
            logging.error(f"Failed to establish SSH tunnel: {e}")
            raise
