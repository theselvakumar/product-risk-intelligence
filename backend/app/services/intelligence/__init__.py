from app.services.intelligence.claim_classifier import ClaimClassifier
from app.services.intelligence.deduplicator import EntityDeduplicator
from app.services.intelligence.ingredient_parser import IngredientParser
from app.services.intelligence.license_extractor import LicenseExtractor
from app.services.intelligence.normalizer import TextNormalizer
from app.services.intelligence.service import ProductIntelligenceService

__all__ = [
    "ProductIntelligenceService",
    "IngredientParser",
    "ClaimClassifier",
    "LicenseExtractor",
    "EntityDeduplicator",
    "TextNormalizer",
]
