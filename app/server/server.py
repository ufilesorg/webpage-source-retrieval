from apps.webpages.routes import router as webpage_router
from fastapi_mongo_base.core import app_factory

from . import config

app = app_factory.create_app(settings=config.Settings(), serve_coverage=False)
app.include_router(webpage_router, prefix=config.Settings.base_path)
