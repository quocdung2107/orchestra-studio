"""Cloud image adapter for APIs that speak OpenAI's `POST /images/generations`.

Dung picks the service (base URL, model, key). Nothing is called unless Dung clicks
"Tạo ảnh" in a project whose image source is `cloud` (ADR-0033). The response may carry
`b64_json` or a `url`; both are handled.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx2

from orchestra_backend.jobs.runner import JobError
from orchestra_backend.media_gateway.meta import (
    CostMeta,
    HardwareReq,
    ImageRequest,
    ImageResult,
    LicenseMeta,
    ProviderMeta,
)

MAX_IMAGE_BYTES = 30 * 1024 * 1024


def meta_for(model: str, base_url: str, commercial_confirmed: bool) -> ProviderMeta:
    return ProviderMeta(
        provider_id="openai_images",
        version=model,
        kind="image",
        label=f"Ảnh cloud ({model} @ {base_url})",
        capabilities={"max_batch": 1},
        hardware=HardwareReq(device="none"),
        # Output rights depend on the provider's terms; Dung confirms them in settings.
        license=LicenseMeta(
            code="service",
            weights="service",
            commercial=True if commercial_confirmed else None,
            output_rights="Theo điều khoản nhà cung cấp (Dung xác nhận)",
            source_url=base_url,
        ),
        cost=CostMeta(local=False),
    )


class OpenAiImages:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        size: str = "1024x1024",
        extra: dict[str, Any] | None = None,
        commercial_confirmed: bool = False,
        transport: httpx2.BaseTransport | None = None,
        timeout_s: float = 180,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.size = size
        self.extra = extra or {}
        self.transport = transport
        self.timeout_s = timeout_s
        self.meta = meta_for(model, self.base_url, commercial_confirmed)

    def _client(self) -> httpx2.Client:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        kw: dict[str, Any] = {"timeout": self.timeout_s, "headers": headers}
        if self.transport is not None:
            kw["transport"] = self.transport
        return httpx2.Client(**kw)

    def generate(self, req: ImageRequest, out: Path) -> ImageResult:
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": req.prompt,
            "n": 1,
            "size": self.size,
        }
        body.update(self.extra)
        try:
            with self._client() as c:
                r = c.post(f"{self.base_url}/images/generations", json=body)
                if r.status_code == 429:
                    raise JobError("image_rate_limited", "Nhà cung cấp ảnh giới hạn tốc độ (429)")
                if r.status_code >= 400:
                    raise JobError(
                        "image_rejected",
                        f"Nhà cung cấp ảnh từ chối ({r.status_code}): {r.text[:500]}",
                        retryable=r.status_code >= 500,
                    )
                data = (r.json().get("data") or [{}])[0]
                if data.get("b64_json"):
                    raw = base64.b64decode(data["b64_json"])
                elif data.get("url"):
                    img = c.get(data["url"])
                    img.raise_for_status()
                    raw = img.content
                else:
                    raise JobError("image_empty", "Phản hồi không có ảnh", retryable=False)
        except httpx2.HTTPError as exc:
            raise JobError("image_unreachable", f"Không gọi được dịch vụ ảnh: {exc}") from exc
        if len(raw) > MAX_IMAGE_BYTES:
            raise JobError("image_too_large", "Ảnh trả về quá lớn", retryable=False)
        out.write_bytes(raw)
        return ImageResult(
            path=out, model=self.model, cost_usd=None, revised_prompt=data.get("revised_prompt")
        )
