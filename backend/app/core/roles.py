from enum import StrEnum


class UserRole(StrEnum):
    """
    Role-Based Access Control (RBAC) hierarchy for DRISHTI.
    Initial role: AUTHORITY_OFFICER.
    Architecturally prepared for ADMIN, SUPERVISOR, REVIEWER.
    """
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    AUTHORITY_OFFICER = "AUTHORITY_OFFICER"
    REVIEWER = "REVIEWER"


# Role permission matrix
ROLE_HIERARCHY = {
    UserRole.ADMIN: [UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.AUTHORITY_OFFICER, UserRole.REVIEWER],
    UserRole.SUPERVISOR: [UserRole.SUPERVISOR, UserRole.AUTHORITY_OFFICER, UserRole.REVIEWER],
    UserRole.AUTHORITY_OFFICER: [UserRole.AUTHORITY_OFFICER, UserRole.REVIEWER],
    UserRole.REVIEWER: [UserRole.REVIEWER],
}
