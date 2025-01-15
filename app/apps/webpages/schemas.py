from typing import Literal

from fastapi_mongo_base.core.enums import Language
from fastapi_mongo_base.schemas import BaseEntitySchema
from fastapi_mongo_base.utils import texttools
from fastapi_mongo_base.tasks import TaskMixin, TaskStatusEnum
from pydantic import BaseModel, Field, field_validator


class WebpageCreateSchema(BaseModel):
    url: str
    force_refetch: bool = False


class WebpageLightSchema(BaseEntitySchema, TaskMixin):
    user_id: str | None = None

    url: str = Field(json_schema_extra={"index": True, "unique": True})
    crawl_method: Literal["direct", "browser"] = "direct"
    screenshot: str | None = None
    google_data: dict | None = None

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
        return f"<{self.__class__.__name__} {self.url}, {self.crawl_method}, {bool(self.brand)}>"


class WebpageSchema(WebpageLightSchema):
    page_source: str | None = None

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
        return self.text and len(self.text) > 150


class WebpageDetailSchema(WebpageSchema):
    text: str | None = None
