import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import UPLOAD_DIR
from app.models.case import AuditLog, Case
from app.models.product import ExtractedInformation, ProductImage
from app.schemas.ocr import (
    CaseOCRSummaryResponse,
    ImageQualityAssessment,
    OCRLine,
    OCRResultResponse,
)
from app.services.ocr.engine import OCREngine
from app.services.ocr.preprocessor import ImagePreprocessor


class OCRService:
    """
    Coordinates image loading, preprocessing, OCR text extraction,
    quality evaluation, and persistence into statutory surveillance records.
    """

    @classmethod
    async def process_image_file(
        cls,
        image_source: Union[str, bytes, Image.Image],
        case_id: uuid.UUID,
        product_id: uuid.UUID,
        image_id: Optional[uuid.UUID] = None,
        db: Optional[AsyncSession] = None,
        current_user_id: Optional[uuid.UUID] = None,
    ) -> OCRResultResponse:
        """
        Execute full OCR workflow for an image:
        1. Validate & load image
        2. Preprocess & evaluate quality (sharpness/blurriness)
        3. Extract text & confidence
        4. Store in extracted_information table
        5. Log immutable audit trail
        """
        now = datetime.now(timezone.utc)

        # 1. Load image
        raw_img = ImagePreprocessor.load_image(image_source)

        # 2. Preprocess & evaluate quality
        enhanced_img, quality_assessment = ImagePreprocessor.preprocess(raw_img)

        # 3. Extract text using OCREngine
        raw_text, confidence, lines = OCREngine.extract_text(
            enhanced_img,
            sharpness_score=quality_assessment.sharpness_score,
        )

        words = raw_text.split()
        word_count = len(words)
        char_count = len(raw_text)

        # Determine processing status
        if quality_assessment.is_blurry or confidence < 0.60:
            status = "LOW_QUALITY_WARNING"
        else:
            status = "SUCCESS"

        extracted_info_id = uuid.uuid4()

        # 4. Persist to database if db session provided
        if db:
            parsed_data: Dict[str, Any] = {
                "quality_assessment": quality_assessment.model_dump(),
                "lines": [l.model_dump() for l in lines],
                "word_count": word_count,
                "character_count": char_count,
                "processing_status": status,
            }

            extracted_record = ExtractedInformation(
                id=extracted_info_id,
                product_id=product_id,
                image_id=image_id,
                zone_type="OCR_FULL_TEXT",
                raw_text=raw_text,
                parsed_data=parsed_data,
                confidence_score=confidence,
                extractor_version=OCREngine.VERSION,
                created_at=now,
            )
            db.add(extracted_record)

            # Audit log entry
            audit = AuditLog(
                case_id=case_id,
                user_id=current_user_id,
                action="OCR_TEXT_EXTRACTED",
                entity_type="ExtractedInformation",
                entity_id=str(extracted_record.id),
                details_json={
                    "image_id": str(image_id) if image_id else None,
                    "confidence": confidence,
                    "word_count": word_count,
                    "is_blurry": quality_assessment.is_blurry,
                    "quality_grade": quality_assessment.quality_grade,
                    "extractor": OCREngine.VERSION,
                },
                created_at=now,
            )
            db.add(audit)
            await db.commit()
            await db.refresh(extracted_record)
            extracted_info_id = extracted_record.id

        return OCRResultResponse(
            extracted_info_id=extracted_info_id,
            case_id=case_id,
            image_id=image_id,
            product_id=product_id,
            zone_type="OCR_FULL_TEXT",
            raw_text=raw_text,
            confidence_score=confidence,
            quality_assessment=quality_assessment,
            lines=lines,
            word_count=word_count,
            character_count=char_count,
            extractor_version=OCREngine.VERSION,
            status=status,
            created_at=now,
        )

    @classmethod
    async def process_case_image(
        cls,
        case_id: uuid.UUID,
        image_id: uuid.UUID,
        db: AsyncSession,
        current_user_id: Optional[uuid.UUID] = None,
    ) -> OCRResultResponse:
        """Process OCR for an existing stored ProductImage in a Case."""
        # 1. Fetch Case
        case_stmt = select(Case).where(Case.id == case_id)
        case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
        if not case_obj:
            raise ValueError(f"Case with ID '{case_id}' not found.")

        # 2. Fetch ProductImage
        img_stmt = select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == case_obj.product_id,
        )
        img_obj = (await db.execute(img_stmt)).scalar_one_or_none()
        if not img_obj:
            raise ValueError(f"ProductImage '{image_id}' not found for case '{case_id}'.")

        # 3. Resolve file path on disk
        # storage_uri looks like /uploads/cases/{case_id}/{filename}
        storage_rel = img_obj.storage_uri.lstrip("/").replace("uploads/", "")
        file_path = os.path.join(UPLOAD_DIR, storage_rel)

        if not os.path.exists(file_path):
            # Fallback: check direct file path
            file_path = os.path.join(UPLOAD_DIR, "cases", str(case_id), os.path.basename(img_obj.storage_uri))

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image asset file not found at: {file_path}")

        return await cls.process_image_file(
            image_source=file_path,
            case_id=case_id,
            product_id=case_obj.product_id,
            image_id=image_id,
            db=db,
            current_user_id=current_user_id,
        )
