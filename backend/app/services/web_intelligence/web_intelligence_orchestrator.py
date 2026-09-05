import logging
import urllib.parse
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.case import AuditLog, Case
from app.models.product import ExtractedInformation, Product, ProductSource
from app.services.web_intelligence.scraping_service import ScrapingService
from app.services.web_intelligence.search_service import SearchResult, SearchService
from app.services.web_intelligence.source_normalizer import SourceNormalizer, WebExtractedData

logger = logging.getLogger(__name__)


@dataclass
class WebIntelligenceSummary:
    """
    Telemetry and audit metrics for the web intelligence collection phase.
    """
    web_collection_attempted: bool = False
    web_sources_found: int = 0
    web_sources_processed: int = 0
    web_collection_success: bool = False
    web_collection_errors: List[str] = field(default_factory=list)
    extracted_sources: List[WebExtractedData] = field(default_factory=list)


class WebIntelligenceOrchestrator:
    """
    Coordinates Level 1 (Product URL) and Level 2 (Public Web Search) intelligence gathering.
    Guarantees that web failures or unreachable pages never break the statutory case pipeline.
    """
    EXTRACTOR_VERSION = "v1.0-DRISHTI-WebIntel"

    @classmethod
    async def collect_case_web_intelligence(
        cls,
        case_id: uuid.UUID,
        product_id: uuid.UUID,
        db: AsyncSession,
        current_user_id: Optional[uuid.UUID] = None,
    ) -> WebIntelligenceSummary:
        now = datetime.now(timezone.utc)
        summary = WebIntelligenceSummary(web_collection_attempted=True)

        if not settings.WEB_INTELLIGENCE_ENABLED:
            logger.info("Web intelligence is disabled in configuration.")
            summary.web_collection_attempted = False
            return summary

        # 1. Resolve Case & Product
        prod_stmt = select(Product).where(Product.id == product_id)
        prod_obj = (await db.execute(prod_stmt)).scalar_one_or_none()
        if not prod_obj:
            summary.web_collection_errors.append(f"Product '{product_id}' not found.")
            return summary

        target_name = prod_obj.product_name or ""
        target_brand = prod_obj.brand or ""
        target_mfr = prod_obj.manufacturer or ""
        target_category = prod_obj.category or ""

        processed_urls = set()

        # -------------------------------------------------------------------
        # Level 1 — Product URL Extraction
        # -------------------------------------------------------------------
        src_stmt = select(ProductSource).where(
            ProductSource.product_id == product_id,
            ProductSource.source_type.in_(["ECOMMERCE_URL", "PRODUCT_URL"]),
        )
        url_sources = (await db.execute(src_stmt)).scalars().all()

        for src in url_sources:
            if not src.source_url:
                continue

            clean_url = src.source_url.strip()
            summary.web_sources_found += 1
            processed_urls.add(clean_url)

            try:
                scraped = await ScrapingService.fetch_and_extract(clean_url)
                if scraped.is_success:
                    extracted = SourceNormalizer.normalize_scraped_page(
                        scraped=scraped,
                        source_type="PRODUCT_URL",
                        target_product_name=target_name,
                        target_brand=target_brand,
                        target_manufacturer=target_mfr,
                    )
                    if extracted:
                        summary.web_sources_processed += 1
                        summary.extracted_sources.append(extracted)

                        # Update existing ProductSource payload with rich structured data
                        existing_payload = src.raw_payload_json or {}
                        if not isinstance(existing_payload, dict):
                            existing_payload = {}

                        existing_payload.update({
                            "title": extracted.title,
                            "raw_content": extracted.raw_content,
                            "description": extracted.raw_content[:500],
                            "ingredients": extracted.ingredients,
                            "claims": extracted.claims,
                            "manufacturer": extracted.manufacturer,
                            "fssai_license_number": extracted.fssai_license_number,
                            "relevance_score": extracted.relevance_score,
                            "relevance_reason": extracted.relevance_reason,
                            "confidence": extracted.confidence,
                            "scraped_at": extracted.extracted_at.isoformat(),
                        })
                        src.raw_payload_json = existing_payload

                        # Persist an ExtractedInformation record for evidentiary provenance
                        extracted_rec = ExtractedInformation(
                            id=uuid.uuid4(),
                            product_id=product_id,
                            image_id=None,
                            zone_type="WEB_PAGE_TEXT",
                            raw_text=extracted.raw_content,
                            parsed_data={
                                "source_url": clean_url,
                                "title": extracted.title,
                                "ingredients": extracted.ingredients,
                                "claims": extracted.claims,
                                "manufacturer": extracted.manufacturer,
                                "fssai_license_number": extracted.fssai_license_number,
                            },
                            confidence_score=extracted.confidence,
                            extractor_version=cls.EXTRACTOR_VERSION,
                        )
                        db.add(extracted_rec)
                else:
                    err_msg = f"URL '{clean_url}' could not be accessed: {scraped.error_message}"
                    summary.web_collection_errors.append(err_msg)
                    logger.info(err_msg)

                    # Record failure inside ProductSource payload without failing the case
                    existing_payload = src.raw_payload_json or {}
                    if isinstance(existing_payload, dict):
                        existing_payload["extraction_error"] = scraped.error_message
                        existing_payload["extraction_attempted_at"] = now.isoformat()
                        src.raw_payload_json = existing_payload

            except Exception as e:
                err_str = f"Error processing product URL '{clean_url}': {e}"
                summary.web_collection_errors.append(err_str)
                logger.warning(err_str)

        # -------------------------------------------------------------------
        # Level 2 — Public Web Information Search
        # -------------------------------------------------------------------
        # Only execute search if we have sufficient product identity
        if target_name and target_name.strip() and target_name != "Product Under Surveillance":
            try:
                search_results: List[SearchResult] = await SearchService.execute_targeted_search(
                    product_name=target_name,
                    brand=target_brand,
                    category=target_category,
                    max_results=settings.MAX_SEARCH_RESULTS,
                )

                scraped_count = 0
                for result in search_results:
                    if result.url in processed_urls:
                        continue
                    if scraped_count >= settings.MAX_PAGES_SCRAPED:
                        break

                    processed_urls.add(result.url)
                    summary.web_sources_found += 1

                    try:
                        scraped_page = await ScrapingService.fetch_and_extract(result.url)
                        if scraped_page.is_success:
                            extracted_web = SourceNormalizer.normalize_scraped_page(
                                scraped=scraped_page,
                                source_type="WEB_SEARCH",
                                target_product_name=target_name,
                                target_brand=target_brand,
                                target_manufacturer=target_mfr,
                            )
                            if extracted_web:
                                scraped_count += 1
                                summary.web_sources_processed += 1
                                summary.extracted_sources.append(extracted_web)

                                parsed_domain = urllib.parse.urlparse(result.url).netloc

                                # Create a new ProductSource entry for this verified web search source
                                new_src = ProductSource(
                                    id=uuid.uuid4(),
                                    product_id=product_id,
                                    source_type="WEB_SEARCH",
                                    source_url=result.url,
                                    platform_name=f"Public Web ({parsed_domain})",
                                    seller_name=extracted_web.manufacturer or None,
                                    raw_payload_json={
                                        "source_type": "WEB_SEARCH",
                                        "source_url": result.url,
                                        "title": extracted_web.title,
                                        "raw_content": extracted_web.raw_content,
                                        "description": extracted_web.raw_content[:500],
                                        "ingredients": extracted_web.ingredients,
                                        "claims": extracted_web.claims,
                                        "manufacturer": extracted_web.manufacturer,
                                        "fssai_license_number": extracted_web.fssai_license_number,
                                        "relevance_score": extracted_web.relevance_score,
                                        "relevance_reason": extracted_web.relevance_reason,
                                        "confidence": extracted_web.confidence,
                                        "search_snippet": result.snippet,
                                        "scraped_at": extracted_web.extracted_at.isoformat(),
                                    },
                                )
                                db.add(new_src)

                                # Also add ExtractedInformation record for evidence trail
                                extracted_web_rec = ExtractedInformation(
                                    id=uuid.uuid4(),
                                    product_id=product_id,
                                    image_id=None,
                                    zone_type="WEB_PAGE_TEXT",
                                    raw_text=extracted_web.raw_content,
                                    parsed_data={
                                        "source_url": result.url,
                                        "title": extracted_web.title,
                                        "ingredients": extracted_web.ingredients,
                                        "claims": extracted_web.claims,
                                        "manufacturer": extracted_web.manufacturer,
                                        "fssai_license_number": extracted_web.fssai_license_number,
                                        "relevance_score": extracted_web.relevance_score,
                                    },
                                    confidence_score=extracted_web.confidence,
                                    extractor_version=cls.EXTRACTOR_VERSION,
                                )
                                db.add(extracted_web_rec)
                        else:
                            summary.web_collection_errors.append(
                                f"Web search page '{result.url}' could not be accessed: {scraped_page.error_message}"
                            )

                    except Exception as page_err:
                        err_str = f"Error processing web search result '{result.url}': {page_err}"
                        summary.web_collection_errors.append(err_str)
                        logger.warning(err_str)

            except Exception as search_err:
                err_str = f"Web search step failed: {search_err}"
                summary.web_collection_errors.append(err_str)
                logger.warning(err_str)

        # Mark success if we either processed sources or encountered no fatal errors
        summary.web_collection_success = (
            summary.web_sources_processed > 0 or len(summary.web_collection_errors) == 0
        )

        try:
            await db.commit()

            # Audit log entry
            audit_entry = AuditLog(
                id=uuid.uuid4(),
                case_id=case_id,
                user_id=current_user_id,
                action="WEB_INTELLIGENCE_COLLECTED",
                entity_type="Case",
                entity_id=str(case_id),
                details_json={
                    "web_sources_found": summary.web_sources_found,
                    "web_sources_processed": summary.web_sources_processed,
                    "web_collection_success": summary.web_collection_success,
                    "error_count": len(summary.web_collection_errors),
                },
                created_at=now,
            )
            db.add(audit_entry)
            await db.commit()

        except Exception as commit_err:
            logger.error("Failed to commit web intelligence records for case '%s': %s", case_id, commit_err)
            summary.web_collection_errors.append(f"Database commit error: {commit_err}")

        return summary
