import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ScrapedPageData:
    """
    Extracted data package from an external web page.
    """
    url: str
    status_code: int = 200
    title: str = ""
    meta_description: str = ""
    readable_text: str = ""
    json_ld_products: List[Dict[str, Any]] = field(default_factory=list)
    raw_content_size_bytes: int = 0
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_success: bool = True
    error_message: Optional[str] = None


class _TextAndMetaExtractor(HTMLParser):
    """
    Zero-dependency HTML parser to safely extract page titles, meta descriptions,
    JSON-LD product schemas, and main text bodies while ignoring scripts/styles.
    """
    IGNORE_TAGS = {"script", "style", "noscript", "svg", "header", "footer", "nav"}

    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.og_title = ""
        self.og_description = ""
        self.json_ld_blocks: List[str] = []
        self.text_chunks: List[str] = []

        self._in_title = False
        self._in_json_ld = False
        self._ignore_stack: List[str] = []
        self._current_json_ld = ""

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag_lower in self.IGNORE_TAGS:
            if tag_lower == "script" and attr_dict.get("type", "").lower() == "application/ld+json":
                self._in_json_ld = True
                self._current_json_ld = ""
            else:
                self._ignore_stack.append(tag_lower)
            return

        if tag_lower == "title":
            self._in_title = True

        elif tag_lower == "meta":
            name = attr_dict.get("name", "").lower()
            prop = attr_dict.get("property", "").lower()
            content = attr_dict.get("content", "").strip()

            if name == "description" and not self.meta_description:
                self.meta_description = content
            elif prop == "og:description" and not self.og_description:
                self.og_description = content
            elif prop == "og:title" and not self.og_title:
                self.og_title = content

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if self._in_json_ld and tag_lower == "script":
            self._in_json_ld = False
            if self._current_json_ld.strip():
                self.json_ld_blocks.append(self._current_json_ld.strip())
            self._current_json_ld = ""
        elif tag_lower in self.IGNORE_TAGS and tag_lower in self._ignore_stack:
            self._ignore_stack.remove(tag_lower)
        elif tag_lower == "title":
            self._in_title = False

    def handle_data(self, data: str):
        if self._in_json_ld:
            self._current_json_ld += data
        elif self._in_title:
            self.title += data
        elif not self._ignore_stack:
            text = data.strip()
            if text:
                self.text_chunks.append(text)


class ScrapingService:
    """
    Ethical, non-intrusive scraping service with strict resource boundaries.
    """

    @classmethod
    async def fetch_and_extract(cls, url: str) -> ScrapedPageData:
        """
        Safely fetches public web content and extracts structured metadata.
        Guarantees that errors (403, 404, timeouts, oversized payloads) are
        returned as structured ScrapedPageData rather than unhandled exceptions.
        """
        if not url or not url.startswith("http"):
            return ScrapedPageData(
                url=url,
                status_code=400,
                is_success=False,
                error_message=f"Invalid URL protocol: '{url}'",
            )

        headers = {
            "User-Agent": settings.SCRAPER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        try:
            async with httpx.AsyncClient(
                timeout=settings.SCRAPER_TIMEOUT_SECONDS,
                follow_redirects=True,
            ) as client:
                response = await client.get(url, headers=headers)
                status_code = response.status_code

                if status_code >= 400:
                    logger.info("Scrape returned HTTP %s for URL: %s", status_code, url)
                    return ScrapedPageData(
                        url=url,
                        status_code=status_code,
                        is_success=False,
                        error_message=f"HTTP Error {status_code}: Unable to access public URL",
                    )

                # Resource protection: Cap content extraction size
                raw_bytes = response.content[:settings.SCRAPER_MAX_CONTENT_BYTES]
                text_content = raw_bytes.decode(response.encoding or "utf-8", errors="replace")

                parser = _TextAndMetaExtractor()
                parser.feed(text_content)

                # Parse JSON-LD blocks for schema.org Product structures
                json_ld_products: List[Dict[str, Any]] = []
                for block in parser.json_ld_blocks:
                    try:
                        data = json.loads(block)
                        if isinstance(data, dict):
                            if data.get("@type") in ("Product", "IndividualProduct", "ProductModel"):
                                json_ld_products.append(data)
                            elif "@graph" in data and isinstance(data["@graph"], list):
                                for item in data["@graph"]:
                                    if isinstance(item, dict) and item.get("@type") == "Product":
                                        json_ld_products.append(item)
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and item.get("@type") == "Product":
                                    json_ld_products.append(item)
                    except Exception:
                        pass  # Invalid JSON-LD block ignored

                resolved_title = parser.og_title or parser.title.strip()
                resolved_desc = parser.og_description or parser.meta_description.strip()
                joined_text = " ".join(parser.text_chunks)

                return ScrapedPageData(
                    url=url,
                    status_code=status_code,
                    title=resolved_title,
                    meta_description=resolved_desc,
                    readable_text=joined_text,
                    json_ld_products=json_ld_products,
                    raw_content_size_bytes=len(raw_bytes),
                    is_success=True,
                )

        except httpx.TimeoutException:
            logger.warning("Scrape timeout (%ss) for URL: %s", settings.SCRAPER_TIMEOUT_SECONDS, url)
            return ScrapedPageData(
                url=url,
                status_code=408,
                is_success=False,
                error_message=f"Request timeout after {settings.SCRAPER_TIMEOUT_SECONDS}s",
            )
        except Exception as exc:
            logger.warning("Scraping error for URL '%s': %s", url, exc)
            return ScrapedPageData(
                url=url,
                status_code=500,
                is_success=False,
                error_message=str(exc),
            )
