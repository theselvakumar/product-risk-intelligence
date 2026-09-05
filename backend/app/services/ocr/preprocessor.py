import io
import math
import os
from typing import Optional, Tuple, Union
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError

from app.schemas.ocr import ImageQualityAssessment


class ImagePreprocessor:
    """
    Image normalization, sharpness evaluation, and quality enhancement pipeline.
    """

    MIN_WIDTH = 50
    MIN_HEIGHT = 50
    BLURRY_THRESHOLD = 18.0

    @classmethod
    def load_image(cls, image_source: Union[str, bytes, io.BytesIO, Image.Image]) -> Image.Image:
        """Safely load and validate image from file path, bytes, or stream."""
        if isinstance(image_source, Image.Image):
            return image_source.copy()

        try:
            if isinstance(image_source, str):
                if not os.path.exists(image_source):
                    raise FileNotFoundError(f"Image file not found at path: {image_source}")
                img = Image.open(image_source)
            elif isinstance(image_source, (bytes, bytearray)):
                if len(image_source) == 0:
                    raise ValueError("Image byte stream is empty (0 bytes).")
                img = Image.open(io.BytesIO(image_source))
            elif isinstance(image_source, io.BytesIO):
                img = Image.open(image_source)
            else:
                raise ValueError(f"Unsupported image source type: {type(image_source)}")

            # Force load image data into memory to catch truncation early
            img.load()
            return img
        except (UnidentifiedImageError, OSError) as e:
            raise ValueError(f"Invalid or corrupted image format: {str(e)}")

    @classmethod
    def evaluate_quality(cls, img: Image.Image) -> ImageQualityAssessment:
        """
        Evaluate resolution, aspect ratio, and sharpness to detect blurry packaging captures.
        """
        width, height = img.size
        channels = len(img.getbands())
        aspect_ratio = round(width / max(height, 1), 2)
        warnings = []

        if width < cls.MIN_WIDTH or height < cls.MIN_HEIGHT:
            warnings.append(f"Image resolution ({width}x{height}) is below recommended minimum.")

        # Compute sharpness score via high-frequency edge transition energy
        gray = ImageOps.grayscale(img)
        from PIL import ImageChops, ImageStat
        diff = ImageChops.difference(gray, gray.filter(ImageFilter.BoxBlur(1)))
        diff_stat = ImageStat.Stat(diff)
        raw_rms = diff_stat.rms[0] if diff_stat.rms else 0.0
        sharpness_score = round(raw_rms * 10.0, 2)

        is_blurry = sharpness_score < cls.BLURRY_THRESHOLD
        if is_blurry:
            warnings.append(f"Image exhibits high blurriness (sharpness score: {sharpness_score} < {cls.BLURRY_THRESHOLD}).")

        # Determine quality grade
        if sharpness_score >= 35.0 and width >= 400 and height >= 400:
            quality_grade = "EXCELLENT"
        elif not is_blurry and width >= 150 and height >= 150:
            quality_grade = "ACCEPTABLE"
        elif is_blurry and width >= 150 and height >= 150:
            quality_grade = "DEGRADED"
        else:
            quality_grade = "POOR"

        return ImageQualityAssessment(
            is_blurry=is_blurry,
            sharpness_score=sharpness_score,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            channels=channels,
            quality_grade=quality_grade,
            warnings=warnings,
        )

    @classmethod
    def preprocess(cls, img: Image.Image) -> Tuple[Image.Image, ImageQualityAssessment]:
        """
        Execute full normalization pipeline:
        1. Auto-orient based on EXIF (if present)
        2. Evaluate quality assessment
        3. Convert to RGB / Grayscale contrast enhancement
        4. Apply adaptive contrast and sharpening filter
        """
        # 1. Correct orientation
        oriented = ImageOps.exif_transpose(img)
        if oriented is None:
            oriented = img

        # 2. Evaluate original quality
        assessment = cls.evaluate_quality(oriented)

        # 3. Enhance for OCR readability
        # Convert to RGB if needed (handling palette, RGBA)
        if oriented.mode not in ("RGB", "L"):
            rgb_img = oriented.convert("RGB")
        else:
            rgb_img = oriented.copy()

        # Boost contrast slightly to distinguish faint label text
        enhancer = ImageEnhance.Contrast(rgb_img)
        contrasted = enhancer.enhance(1.25)

        # Sharpen edges
        sharpened = contrasted.filter(ImageFilter.SHARPEN)

        return sharpened, assessment
