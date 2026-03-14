from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.config import settings


@dataclass
class CollectedPage:
    platform: str
    url: str
    raw_fields: dict
    screenshot_urls: list[str]
    snapshot_id: str


class OpenClawAdapter:
    """OpenClaw collector adapter.

    `mock` mode is default for local prototype.
    `remote` mode allows pointing to a dedicated Mac collector host.
    """

    def __init__(self) -> None:
        self.mode = settings.openclaw_mode
        self.remote_base_url = settings.openclaw_remote_base_url.rstrip("/")
        self.timeout = settings.openclaw_timeout_seconds

    def collect(self, platform: str, url: str, template_version: str) -> CollectedPage:
        if self.mode == "remote":
            return self._collect_remote(platform=platform, url=url, template_version=template_version)
        return self._collect_mock(platform=platform, url=url, template_version=template_version)

    def _collect_mock(self, platform: str, url: str, template_version: str) -> CollectedPage:
        base_price = 3299
        coupon = 100
        gift_items: list[str] = []

        platform_lower = platform.lower()
        if "jd" in platform_lower:
            base_price = 3199
            coupon = 200
            gift_items = ["earbuds"]
        elif "taobao" in platform_lower or "tmall" in platform_lower:
            base_price = 3299
            coupon = 100
        elif "pdd" in platform_lower or "pinduoduo" in platform_lower:
            base_price = 3099
            coupon = 50
            gift_items = ["screen protector"]

        final_price = base_price - coupon
        raw_fields = {
            "template_version": template_version,
            "price_text": f"base price {base_price}",
            "coupon_text": f"coupon {coupon}",
            "gift_text": ", ".join(gift_items),
            "final_price_text": f"final price {final_price}",
        }
        snapshot_id = f"snap_{abs(hash(url + platform)) % 99999}"
        screenshot_urls = [f"https://example.invalid/{snapshot_id}.png"]

        return CollectedPage(
            platform=platform,
            url=url,
            raw_fields=raw_fields,
            screenshot_urls=screenshot_urls,
            snapshot_id=snapshot_id,
        )

    def _collect_remote(self, platform: str, url: str, template_version: str) -> CollectedPage:
        endpoint = f"{self.remote_base_url}/api/v1/collect"
        payload = {
            "platform": platform,
            "url": url,
            "template_version": template_version,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

        # Allow tolerant parsing for early prototype compatibility.
        raw_fields = data.get("raw_fields") or {}
        snapshot_id = data.get("snapshot_id") or f"remote_{abs(hash(url)) % 99999}"
        screenshot_urls = data.get("screenshot_urls") or []

        return CollectedPage(
            platform=platform,
            url=url,
            raw_fields=raw_fields,
            screenshot_urls=screenshot_urls,
            snapshot_id=snapshot_id,
        )


def normalize_offer(platform: str, raw_fields: dict) -> dict:
    def parse_int(text: str) -> int:
        match = re.search(r"(\d+)", text or "")
        return int(match.group(1)) if match else 0

    base_price = parse_int(raw_fields.get("price_text", ""))
    coupon = parse_int(raw_fields.get("coupon_text", ""))
    gift_text = raw_fields.get("gift_text", "")
    gift_items = [item.strip() for item in gift_text.split(",") if item.strip()]
    final_price = parse_int(raw_fields.get("final_price_text", "")) or max(base_price - coupon, 0)

    issue_flags: list[str] = []
    if base_price == 0:
        issue_flags.append("missing_base_price")

    confidence = 0.9 if not issue_flags else 0.6

    return {
        "platform": platform,
        "base_price": base_price,
        "coupon_discount": coupon,
        "gift_items": gift_items,
        "final_price": final_price,
        "issue_flags": issue_flags,
        "confidence": confidence,
    }
