import datetime
import uuid
from typing import Literal

from fastapi_mongo_base.schemas import BaseEntitySchema
from fastapi_mongo_base.tasks import TaskMixin
from pydantic import BaseModel, Field, field_validator


class WebpageCreateSchema(BaseModel):
    url: str
    force_refetch: bool = False
    meta_data: dict = {}


class WebpageSchema(BaseEntitySchema, TaskMixin):
    user_id: uuid.UUID | None = None

    url: str = Field(json_schema_extra={"index": True, "unique": True})
    crawl_method: Literal["direct", "browser"] = "direct"
    images: list[str] | None = None

    # screenshot: str | None = None
    # google_data: dict | None = None

    @property
    def page_source(self):
        from server.db import redis_sync as redis

        value = redis.get(f"WEBPAGE:source:{self.url}")
        if value:
            return value.decode("utf-8")
        return None

    @page_source.setter
    def page_source(self, value: str):
        from server.db import redis_sync as redis

        redis.set(f"WEBPAGE:source:{self.url}", str(value), ex=60 * 60 * 4)

    def expired(self, hours: int = 4):
        return (
            datetime.datetime.now() - self.updated_at
        ).total_seconds() / 3600 > hours

    @field_validator("url")
    def validate_url(cls, value: str):
        if not value.startswith("http"):
            value = f"https://{value}"
        return value

    @property
    def main_domain(self):
        from .services import get_main_domain

        return get_main_domain(self.url)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.url}, {self.crawl_method}>"

    def check_cache(self):
        return self.page_source and not self.expired()

    @property
    def soup(self):
        from bs4 import BeautifulSoup

        if self.page_source is None:
            return None
        return BeautifulSoup(self.page_source, "html.parser")

    @property
    def text(self):
        from fastapi_mongo_base.utils import texttools

        if not self.soup:
            return ""
        text_content = self.soup.get_text(separator=" ").strip()
        return texttools.remove_whitespace(text_content)

    @property
    def meta_text(self):
        if not self.soup:
            return
        return "\n".join(
            [
                tag.get("content")
                for tag in self.soup.find_all("meta")
                if tag.get("content")
            ]
        )

    @property
    def title(self):
        if not self.soup:
            return
        title = self.soup.find("title")
        if title:
            return title.get_text().strip()

    def is_enough_text(self):
        return self.text and len(self.text) > 500


class WebpageListSchema(BaseEntitySchema, TaskMixin):
    user_id: uuid.UUID | None = None

    url: str = Field(json_schema_extra={"index": True, "unique": True})
    crawl_method: Literal["direct", "browser"] = "direct"
    title: str | None = None
    main_domain: str | None = None
    meta_text: str | None = None


class WebpageDetailSchema(WebpageSchema):
    text: str | None = None
