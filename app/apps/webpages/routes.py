import uuid

from fastapi import BackgroundTasks, Request
from fastapi_mongo_base.routes import AbstractTaskRouter
from usso.fastapi.integration import jwt_access_security

from .models import Webpage
from .schemas import (
    WebpageCreateSchema,
    WebpageDetailSchema,
    WebpageListSchema,
    WebpageSchema,
)
from .services import images_from_webpage


class WebpageRouter(AbstractTaskRouter[Webpage, WebpageSchema]):
    def __init__(self):
        super().__init__(
            model=Webpage, schema=WebpageSchema, user_dependency=jwt_access_security
        )

    def config_schemas(self, schema, **kwargs):
        super().config_schemas(schema, list_item_schema=WebpageListSchema, **kwargs)
        self.retrieve_response_schema = WebpageDetailSchema  # WebpageSchema

    def config_routes(self, **kwargs):
        self.router.add_api_route(
            "/",
            self.list_items,
            methods=["GET"],
            response_model=self.list_response_schema,
            status_code=200,
        )
        self.router.add_api_route(
            "/{uid:uuid}",
            self.retrieve_item,
            methods=["GET"],
            response_model=self.retrieve_response_schema,
            status_code=200,
        )
        self.router.add_api_route(
            "/",
            self.create_item,
            methods=["POST"],
            response_model=self.create_response_schema,
            status_code=201,
        )
        self.router.add_api_route(
            "/{uid:uuid}/text",
            self.get_text,
            methods=["GET"],
        )
        self.router.add_api_route(
            "/{uid:uuid}/images",
            self.get_images,
            methods=["GET"],
            # include_in_schema=False,
        )
        # self.router.add_api_route(
        #     "/{uid:uuid}/{action:str}",
        #     self.action,
        #     methods=["GET"],
        #     # include_in_schema=False,
        # )

    async def retrieve_item(self, request: Request, uid: uuid.UUID):
        return await super().retrieve_item(request, uid)

    async def create_item(
        self,
        request: Request,
        data: WebpageCreateSchema,
        background_tasks: BackgroundTasks,
        # sync: bool = False,
    ):
        webpage: Webpage = await Webpage.get_by_url(data.url)
        if not webpage:
            webpage: Webpage = await super(AbstractTaskRouter, self).create_item(
                request, data.model_dump()
            )

        if data.force_refetch:
            webpage.page_source = None
            webpage.task_status = "init"

        if False:
            await webpage.start_processing(force_refetch=data.force_refetch)
        else:
            # background_tasks.add_task(
            #     webpage.start_processing, force_refetch=data.force_refetch
            # )
            await webpage.push_to_queue(**data.model_dump())

        return webpage

    async def get_text(self, request: Request, uid: uuid.UUID):
        item: Webpage = await self.get_item(uid)
        return {"text": item.text}

    async def get_images(
        self,
        request: Request,
        uid: uuid.UUID,
        # invalid_languages: str | None = None,
        # min_acceptable_side: int = 600,
        # max_acceptable_side: int = 2500,
        # with_svg: bool = False,
    ):
        item: Webpage = await self.get_item(uid)
        return {"images": item.images}
        {
            "images": await images_from_webpage(
                item,
                invalid_languages=invalid_languages,
                min_acceptable_side=min_acceptable_side,
                max_acceptable_side=max_acceptable_side,
                with_svg=with_svg,
            )
        }


router = WebpageRouter().router
