import uuid

from fastapi import BackgroundTasks, Request
from fastapi_mongo_base.routes import AbstractTaskRouter

from .models import Webpage
from .schemas import WebpageCreateSchema, WebpageDetailSchema, WebpageLightSchema


class WebpageRouter(AbstractTaskRouter[Webpage, WebpageLightSchema]):
    def __init__(self):
        super().__init__(model=Webpage, schema=WebpageLightSchema, user_dependency=None)

    def config_schemas(self, schema, **kwargs):
        super().config_schemas(schema, **kwargs)
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
            include_in_schema=False,
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
        sync: bool = False,
    ):
        webpage: Webpage = await Webpage.get_by_url(data.url)
        if not webpage:
            return await super().create_item(
                request, data.model_dump(), background_tasks
            )

        if data.force_refetch:
            webpage.page_source = None
            webpage.task_status = "init"

        if sync:
            await webpage.start_processing(force_refetch=data.force_refetch)
        else:
            background_tasks.add_task(
                webpage.start_processing, force_refetch=data.force_refetch
            )

        return webpage

    async def get_text(self, request: Request, uid: uuid.UUID):
        item: Webpage = await self.get_item(uid)
        return {"text": item.text}

    async def get_images(self, request: Request, uid: uuid.UUID):
        raise NotImplementedError

router = WebpageRouter().router
