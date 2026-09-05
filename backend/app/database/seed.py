import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import UserRole
from app.core.security import hash_password
from app.models.analysis import RiskAssessment
from app.models.case import Case
from app.models.product import Product
from app.models.user import User

DEV_OFFICER_EMAIL = "officer@drishti.gov.in"
DEV_OFFICER_PASSWORD = "AuthorityOfficer2026!"
DEV_OFFICER_BADGE = "FSO-DL-CENTRAL-012"


async def seed_authority_officer(db: AsyncSession) -> User:
    """Ensure development authority officer seed user exists."""
    stmt = select(User).where(User.email == DEV_OFFICER_EMAIL)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email=DEV_OFFICER_EMAIL,
            full_name="Rajesh Sharma (Food Safety Officer)",
            badge_id=DEV_OFFICER_BADGE,
            role=UserRole.AUTHORITY_OFFICER,
            jurisdiction_state="DL",
            jurisdiction_district="DL-CENTRAL",
            is_active=True,
            hashed_password=hash_password(DEV_OFFICER_PASSWORD),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


async def seed_demonstration_cases(db: AsyncSession, officer: User):
    """Seed demonstration cases, products, and risk assessments for the regulatory dashboard."""
    # Check if demo cases already exist
    stmt = select(Case).limit(1)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        return

    now = datetime.now(timezone.utc)

    demo_data = [
        {
            "product_name": "AyurVital Diabetic Care Shake",
            "brand": "AyurVital Health",
            "category": "HEALTH_SUPPLEMENTS_AND_NUTRACEUTICALS",
            "manufacturer": "AyurVital Labs Pvt Ltd",
            "fssai_license": "11221334000567",
            "case_number": "FSSAI-CASE-2026-0042",
            "title": "Illegal Curative Diabetes Claim on AyurVital Shake",
            "priority": "URGENT_P1",
            "status": "FIELD_INSPECTION_ORDERED",
            "risk_score": 88.5,
            "risk_level": "CRITICAL",
            "days_ago": 1,
        },
        {
            "product_name": "PureKeto Energy Bar Deluxe",
            "brand": "NutriPure Brands",
            "category": "CEREAL_AND_CONFECTIONERY",
            "manufacturer": "NutriPure Foods Ltd",
            "fssai_license": "10018022007890",
            "case_number": "FSSAI-CASE-2026-0043",
            "title": "Undeclared High Added Sugars (18g vs 0g Web Claim)",
            "priority": "HIGH_P2",
            "status": "NOTICE_ISSUED_SEC32",
            "risk_score": 76.0,
            "risk_level": "HIGH",
            "days_ago": 2,
        },
        {
            "product_name": "Himalayan Shilajit Pure Resin",
            "brand": "MountainHerbs",
            "category": "AYURVEDIC_PROPRIETARY",
            "manufacturer": "Himalayan BioLabs",
            "fssai_license": "11022011000123",
            "case_number": "FSSAI-CASE-2026-0044",
            "title": "Unsubstantiated Stamina & Anti-Aging Claims",
            "priority": "ROUTINE_P3",
            "status": "TRIAGED",
            "risk_score": 52.0,
            "risk_level": "MEDIUM",
            "days_ago": 3,
        },
        {
            "product_name": "Organic Cold-Pressed Mustard Oil",
            "brand": "BharatAgro",
            "category": "EDIBLE_OILS_AND_FATS",
            "manufacturer": "Bharat Agro Mills",
            "fssai_license": "10014011002345",
            "case_number": "FSSAI-CASE-2026-0045",
            "title": "Routine Market Surveillance Sample - Compliant",
            "priority": "MONITORING_P4",
            "status": "RESOLVED",
            "risk_score": 18.0,
            "risk_level": "LOW",
            "days_ago": 4,
        },
        {
            "product_name": "NutriGrow Fortified Infant Formula",
            "brand": "EarlyCare",
            "category": "INFANT_FOODS_AND_FORMULA",
            "manufacturer": "EarlyCare Nutrition International",
            "fssai_license": "10020044001928",
            "case_number": "FSSAI-CASE-2026-0046",
            "title": "Excess Vitamin A Exceeding Tolerable Upper Limit (RDA 2022)",
            "priority": "URGENT_P1",
            "status": "SAMPLE_DRAWN",
            "risk_score": 84.0,
            "risk_level": "CRITICAL",
            "days_ago": 5,
        },
        {
            "product_name": "Herbal Glow Ayurvedic Detox Tea",
            "brand": "GreenLeaf",
            "category": "BEVERAGES_TEA_AND_COFFEE",
            "manufacturer": "GreenLeaf Botanicals",
            "fssai_license": "11519033000456",
            "case_number": "FSSAI-CASE-2026-0047",
            "title": "Missing Mandatory Warning on Senna Leaves Content",
            "priority": "ROUTINE_P3",
            "status": "ASSIGNED",
            "risk_score": 45.0,
            "risk_level": "MEDIUM",
            "days_ago": 6,
        },
    ]

    for item in demo_data:
        prod = Product(
            product_name=item["product_name"],
            brand=item["brand"],
            category=item["category"],
            manufacturer=item["manufacturer"],
            fssai_license_number=item["fssai_license"],
        )
        db.add(prod)
        await db.flush()

        case_obj = Case(
            case_number=item["case_number"],
            product_id=prod.id,
            assigned_user_id=officer.id,
            status=item["status"],
            priority=item["priority"],
            jurisdiction_district="DL-CENTRAL",
            title=item["title"],
            created_at=now - timedelta(days=item["days_ago"]),
        )
        db.add(case_obj)
        await db.flush()

        risk_obj = RiskAssessment(
            product_id=prod.id,
            case_id=case_obj.id,
            risk_score=item["risk_score"],
            risk_level=item["risk_level"],
            confidence_score=0.95,
            health_hazard_score=item["risk_score"] * 0.9,
            deception_score=item["risk_score"] * 0.85,
            licensing_score=item["risk_score"] * 0.7,
        )
        db.add(risk_obj)

    await db.commit()
