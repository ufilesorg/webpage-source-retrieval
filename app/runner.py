import asyncio
import logging
import os
import signal
from typing import Type, TypeVar

import json_advanced as json
from apps.webpages import models
from fastapi_mongo_base.models import BaseEntityTaskMixin
from server import config, db

T = TypeVar("T", bound=BaseEntityTaskMixin)


async def initialize_app():
    from fastapi_mongo_base.core import db

    os.getenv("HOSTNAME", "unknown")

    config.Settings.config_logger()  # f"{worker_id}.log")
    await db.init_mongo_db()
    logging.info("Worker initialized")


async def process_queue_message(entity_class: Type[T], **kwargs):
    queue_name = kwargs.get("name", entity_class.__name__).lower() + "_queue"
    redis_client = await db.RedisSSHHandler().initialize()
    await asyncio.wait_for(redis_client.ping(), timeout=10)
    # logging.info(f"Connected to Redis")
    result = await redis_client.brpop(queue_name, timeout=300)  # 5 minutes timeout
    logging.info(f"Received message from {result} {queue_name}")
    if result:
        _, message = result  # Unpack the queue_name and message
        data = json.loads(message.decode("utf-8"))
        uid = data.get("uid")
        entity = await entity_class.get_item(uid)
        # async with httpx.AsyncClient(
        #     headers={"x-api-key": os.getenv("UFILES_API_KEY")}
        # ) as client:
        #     uid = data.get("uid")
        #     response = await client.get(
        #         url=f"https://{config.Settings.root_url}{config.Settings.base_path}/webpages/{uid}",
        #     )
        #     if response.status_code == 200:
        #         entity = entity_class(**response.json())
        #         await entity.start_processing()
        #         return True

        await entity.start_processing()

        if data.get("meta_data", {}).get("get_images", True):
            logging.info(f"Getting images for {entity.uid}")
            from apps.webpages import services
            from fastapi_mongo_base.core import enums

            urls = await services.images_from_webpage(
                entity,
                invalid_languages=data.get("meta_data", {}).get(
                    "invalid_languages", [enums.Language.Persian]
                ),
                min_acceptable_side=data.get("meta_data", {}).get(
                    "min_acceptable_side", 600
                ),
                max_acceptable_side=data.get("meta_data", {}).get(
                    "max_acceptable_side", 2500
                ),
                with_svg=data.get("meta_data", {}).get("with_svg", False),
            )
            entity.images = urls
            await entity.save()
        else:
            logging.info(f"Skipping images for {entity.uid}")
    return False


async def start_workers():
    """Start the worker processes"""
    await initialize_app()

    while True:
        try:
            success = await process_queue_message(
                entity_class=models.Webpage,
                name=models.Webpage.__name__,
            )
            if not success:
                logging.info("No message received after timeout")
        except asyncio.CancelledError:
            logging.info("Worker cancelled, shutting down...")
            break


def handle_shutdown(signum, frame):
    """Handle shutdown signals"""
    logging.info(f"Received signal {signum}. Starting graceful shutdown...")
    # Raise KeyboardInterrupt to trigger the cleanup in the main try/except block
    raise KeyboardInterrupt


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    # Note: SIGKILL (9) cannot be caught or ignored

    try:
        # Start worker processes
        asyncio.run(start_workers())
    except KeyboardInterrupt:
        logging.info("Received shutdown signal, initiating graceful shutdown...")
    except Exception as e:
        import traceback

        logging.error(traceback.format_exc())
        logging.error(f"Error starting workers: {type(e)} {e}")
    finally:
        logging.info("Worker shutdown")
