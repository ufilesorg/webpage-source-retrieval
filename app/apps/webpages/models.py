import re
from urllib.parse import urlparse

from fastapi_mongo_base.models import BaseEntity
from pymongo import ASCENDING, IndexModel

from .schemas import WebpageSchema


class Webpage(WebpageSchema, BaseEntity):
    class Settings:
        indexes = BaseEntity.Settings.indexes + [
            IndexModel([("url", ASCENDING)], unique=True),
        ]

    @classmethod
    async def get_by_url(cls, url: str, *, skip_uid=None) -> "Webpage":
        parsed = urlparse(url)
        netloc = parsed.netloc
        path = parsed.path or "/"
        query = parsed.query

        webpages = await cls.search_by_url(netloc)
        for webpage in webpages:
            if skip_uid and webpage.uid == skip_uid:
                continue
            webpage_parsed = urlparse(webpage.url)
            webpage_netloc = webpage_parsed.netloc
            webpage_path = webpage_parsed.path or "/"
            webpage_query = webpage_parsed.query
            if (
                netloc == webpage_netloc
                and path == webpage_path
                and query == webpage_query
            ):
                return webpage

        return await cls.find_one(cls.url == url)

    @classmethod
    async def search_by_url(cls, partial_url) -> list["Webpage"]:
        escaped_partial_url = re.escape(partial_url)
        pattern = re.compile(rf".*{escaped_partial_url}.*", re.IGNORECASE)
        query = {"url": {"$regex": pattern}}
        results: list[Webpage] = await Webpage.find(query).to_list()
        return results

    async def start_processing(self, **kwargs):
        from . import services

        return await services.fetch_webpage(self, **kwargs)

    async def push_to_queue(self, **kwargs):
        """Add the task to Redis queue"""
        import json

        from server import db

        queue_name = f"{self.__class__.__name__.lower()}_queue"
        await db.redis.lpush(
            queue_name,
            json.dumps(kwargs | self.model_dump(include={"uid"}, mode="json")),
        )
