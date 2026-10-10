"""Identity-owned evidence on local disk, optionally replicated to S3-compatible storage."""

import hashlib
from pathlib import Path
import shutil
import boto3
from botocore.config import Config


class EvidenceStore:
    def __init__(self, settings):
        self.root = settings.data_dir
        self.bucket = settings.obj_bucket
        self.client = None
        self.remote_verified = False
        if settings.object_storage_configured:
            self.client = boto3.client(
                "s3",
                endpoint_url=settings.obj_endpoint,
                aws_access_key_id=settings.obj_access_key.get_secret_value(),
                aws_secret_access_key=settings.obj_secret_key.get_secret_value(),
                config=Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 1}),
            )

    def put(self, person_id, filename, payload):
        relative = Path("people") / person_id / filename
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        try:
            if self.client:
                self.client.put_object(Bucket=self.bucket, Key=str(relative), Body=payload)
                self.remote_verified = True
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return {
            "path": str(relative),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_length": len(payload),
            "storage": "s3_and_local" if self.client else "local",
            "object_key": str(relative) if self.client else None,
        }

    def remove_files(self, records):
        for item in records:
            if self.client and item.get("object_key"):
                self.client.delete_object(Bucket=self.bucket, Key=item["object_key"])
            (self.root / item["path"]).unlink(missing_ok=True)

    def delete_person(self, person_id):
        prefix = f"people/{person_id}/"
        if self.client:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                objects = [{"Key": row["Key"]} for row in page.get("Contents", [])]
                if objects:
                    result = self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
                    if result.get("Errors"):
                        raise RuntimeError("Object storage did not delete all person evidence")
        directory = self.root / "people" / person_id
        if directory.exists():
            shutil.rmtree(directory)


async def capture_page(storage, person_id, case_id, page_url, image_record, captured_at):
    """All browser requests are fulfilled through the same GET-only robots guard."""
    import asyncio
    import json
    import uuid
    from playwright.async_api import async_playwright
    from censearch.agent.web import ReadOnlyWeb, UA

    web = ReadOnlyWeb(limit=60)
    capture_id = uuid.uuid4().hex
    prefix = f"evidence/case-{case_id}-{capture_id}"
    page_headers = {}
    pending = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                context = await browser.new_context(
                    user_agent=UA, service_workers="block", accept_downloads=False
                )

                async def intercept(route):
                    if route.request.method != "GET":
                        await route.abort()
                        return
                    try:
                        response = await asyncio.to_thread(web.get, route.request.url)
                        headers = dict(response.headers)
                        for key in ("content-length", "content-encoding", "transfer-encoding"):
                            headers.pop(key, None)
                        await route.fulfill(
                            status=response.status_code, headers=headers, body=response.content
                        )
                    except Exception:
                        await route.abort()

                await context.route("**/*", intercept)
                await context.route_web_socket("**/*", lambda socket: socket.close())
                page = await context.new_page()
                response = await page.goto(page_url, wait_until="networkidle", timeout=15000)
                if response is None or response.status != 200:
                    raise ValueError("Cannot capture a successful evidence page")
                page_headers = await response.all_headers()
                screenshot = await page.screenshot(full_page=True)
                final_url = page.url
            finally:
                await browser.close()
        image_bytes = (storage.root / image_record["path"]).read_bytes()
        if hashlib.sha256(image_bytes).hexdigest() != image_record["sha256"]:
            raise ValueError("Retained matched image hash mismatch")
        shot = await asyncio.to_thread(storage.put, person_id, prefix + ".png", screenshot)
        pending.append(shot)
        bundle = {
            "page_url": page_url,
            "final_url": final_url,
            "captured_at": captured_at,
            "image": image_record,
            "image_sha256": image_record["sha256"],
            "screenshot": shot,
            "page_response_headers": page_headers,
            "requests": web.trace,
            "screenshot_url": f"/api/cases/{case_id}/screenshot",
        }
        bundle_file = await asyncio.to_thread(
            storage.put, person_id, prefix + ".json", json.dumps(bundle, indent=2).encode()
        )
        pending.append(bundle_file)
        return bundle | {"bundle_file": bundle_file}
    except BaseException:
        await asyncio.to_thread(storage.remove_files, pending)
        raise
    finally:
        web.close()
