import abc
import logging
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """
    Standardized search result item with attribution.
    """
    title: str
    url: str
    snippet: str
    source_engine: str = "duckduckgo"
    rank: int = 1


class BaseSearchProvider(abc.ABC):
    """
    Abstract interface for pluggable search engines.
    """
    @abc.abstractmethod
    async def search(self, query: str, max_results: int = 3) -> List[SearchResult]:
        """Execute a search query and return ranked results."""
        pass


class _DDGHTMLParser(HTMLParser):
    """
    Lightweight, dependency-free HTML parser for DuckDuckGo HTML search results.
    """
    def __init__(self, max_results: int = 3):
        super().__init__()
        self.max_results = max_results
        self.results: List[SearchResult] = []
        self._in_result_title = False
        self._in_result_snippet = False
        self._current_title = ""
        self._current_url = ""
        self._current_snippet = ""

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        attr_dict = dict(attrs)
        class_name = attr_dict.get("class", "")

        if tag == "a" and "result__url" in class_name:
            href = attr_dict.get("href", "")
            # Extract actual URL if wrapped in DuckDuckGo redirect uddg parameter
            if "uddg=" in href:
                parsed = urllib.parse.urlparse(href)
                qs = urllib.parse.parse_qs(parsed.query)
                actual_url = qs.get("uddg", [href])[0]
            else:
                actual_url = href
            if actual_url.startswith("http"):
                self._current_url = actual_url

        elif tag == "a" and "result__snippet" in class_name:
            self._in_result_snippet = True
            self._current_snippet = ""

        elif tag == "h2" and "result__title" in class_name:
            self._in_result_title = True
            self._current_title = ""

    def handle_endtag(self, tag: str):
        if tag == "h2" and self._in_result_title:
            self._in_result_title = False
        elif tag == "a" and self._in_result_snippet:
            self._in_result_snippet = False
            # If we have title, URL, or snippet collected, save result
            if self._current_url and len(self.results) < self.max_results:
                clean_title = self._current_title.strip() or "Product Search Result"
                clean_snippet = self._current_snippet.strip()
                self.results.append(
                    SearchResult(
                        title=clean_title,
                        url=self._current_url,
                        snippet=clean_snippet,
                        source_engine="duckduckgo",
                        rank=len(self.results) + 1,
                    )
                )
                self._current_title = ""
                self._current_url = ""
                self._current_snippet = ""

    def handle_data(self, data: str):
        if self._in_result_title:
            self._current_title += data
        elif self._in_result_snippet:
            self._current_snippet += data


class DuckDuckGoSearchProvider(BaseSearchProvider):
    """
    Production-ready privacy-respecting search provider using DuckDuckGo HTML interface.
    """
    DDG_ENDPOINT = "https://html.duckduckgo.com/html/"

    async def search(self, query: str, max_results: int = 3) -> List[SearchResult]:
        if not query or not query.strip():
            return []

        headers = {
            "User-Agent": settings.SCRAPER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        data = {"q": query.strip(), "b": ""}

        try:
            async with httpx.AsyncClient(
                timeout=settings.SCRAPER_TIMEOUT_SECONDS,
                follow_redirects=True,
            ) as client:
                res = await client.post(self.DDG_ENDPOINT, data=data, headers=headers)
                if res.status_code != 200:
                    logger.warning("DuckDuckGo search returned HTTP %s for query '%s'", res.status_code, query)
                    return []

                parser = _DDGHTMLParser(max_results=max_results)
                parser.feed(res.text)
                return parser.results

        except Exception as err:
            logger.warning("DuckDuckGo search error for query '%s': %s", query, err)
            return []


class MockSearchProvider(BaseSearchProvider):
    """
    Deterministic mock search provider for unit tests and offline CI environments.
    """
    def __init__(self, predefined_results: Optional[Dict[str, List[SearchResult]]] = None):
        self.predefined_results = predefined_results or {}
        self.search_history: List[str] = []

    async def search(self, query: str, max_results: int = 3) -> List[SearchResult]:
        self.search_history.append(query)
        # Check exact or keyword match in predefined results
        for key, items in self.predefined_results.items():
            if key.lower() in query.lower():
                return items[:max_results]

        # Generate synthetic realistic search results based on query keywords
        domain_safe = urllib.parse.quote_plus(query.lower())
        return [
            SearchResult(
                title=f"{query.title()} - Official Product Information",
                url=f"https://marketplace.example.com/products/{domain_safe}",
                snippet=f"Detailed product specifications, declared ingredients, and statutory claims for {query}.",
                source_engine="mock_engine",
                rank=1,
            ),
            SearchResult(
                title=f"{query.title()} on HealthKart Surveillance Desk",
                url=f"https://retailer.example.com/items/{domain_safe}",
                snippet=f"Complete packaging review and nutritional composition for {query}.",
                source_engine="mock_engine",
                rank=2,
            ),
        ][:max_results]


class SearchService:
    """
    Search orchestration service with provider factory and query synthesis.
    """
    _provider_instance: Optional[BaseSearchProvider] = None

    @classmethod
    def get_provider(cls) -> BaseSearchProvider:
        if cls._provider_instance is not None:
            return cls._provider_instance

        provider_name = (settings.SEARCH_PROVIDER or "duckduckgo").lower()
        if provider_name == "mock":
            cls._provider_instance = MockSearchProvider()
        else:
            cls._provider_instance = DuckDuckGoSearchProvider()

        return cls._provider_instance

    @classmethod
    def set_provider(cls, provider: BaseSearchProvider) -> None:
        """Inject custom provider for tests or specific runtime configurations."""
        cls._provider_instance = provider

    @classmethod
    def reset_provider(cls) -> None:
        cls._provider_instance = None

    @classmethod
    def generate_search_queries(
        cls,
        product_name: str,
        brand: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[str]:
        """
        Synthesizes controlled, high-precision search queries to avoid blind web queries.
        """
        queries: List[str] = []
        clean_name = product_name.strip() if product_name else ""
        clean_brand = brand.strip() if brand else ""

        if clean_brand and clean_name and clean_brand.lower() not in clean_name.lower():
            queries.append(f"{clean_brand} {clean_name}")
        elif clean_name:
            queries.append(clean_name)

        # Secondary query targeting ingredients & statutory labelling if name is specific
        if clean_name and len(clean_name.split()) >= 2:
            queries.append(f"{clean_name} ingredients")

        # Cap to max 2 queries
        return queries[:2]

    @classmethod
    async def execute_targeted_search(
        cls,
        product_name: str,
        brand: Optional[str] = None,
        category: Optional[str] = None,
        max_results: int = 3,
    ) -> List[SearchResult]:
        """
        Executes controlled search queries and aggregates unique results.
        """
        queries = cls.generate_search_queries(product_name, brand, category)
        provider = cls.get_provider()
        all_results: List[SearchResult] = []
        seen_urls = set()

        for q in queries:
            try:
                results = await provider.search(q, max_results=max_results)
                for r in results:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append(r)
                        if len(all_results) >= max_results:
                            break
            except Exception as e:
                logger.warning("Search query '%s' failed: %s", q, e)

            if len(all_results) >= max_results:
                break

        return all_results
