"""Serve the built product and the optional operator console on the API origin."""

from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def install_frontend(app, settings):
    # API routes are installed first so missing assets never hide API failures.
    if (settings.console_dir / "index.html").is_file():
        app.mount("/console", FrontendFiles(directory=settings.console_dir, html=True), name="console")
    if (settings.frontend_dir / "index.html").is_file():
        app.mount("/", FrontendFiles(directory=settings.frontend_dir, html=True), name="frontend")
    else:
        @app.get("/", include_in_schema=False)
        @app.get("/app/", include_in_schema=False)
        def frontend_missing():
            return JSONResponse(status_code=503, content={"error": {
                "code": "frontend_not_built",
                "message": "Build the frontend with: npm --prefix frontend ci && npm --prefix frontend run build",
            }})
