"""SQLAlchemy ORM 模型。

按业务域组织：
- users
- properties
- demands
- invitations
- proposals
- cooperations
- reviews
"""

from app.models.base import SoftDeleteMixin, TimestampMixin
from app.models.cooperation import Cooperation, CooperationStatus
from app.models.demand import Demand, DemandStatus
from app.models.device import Device
from app.models.invitation import Invitation, InvitationStatus
from app.models.property import Property, PropertyStatus
from app.models.proposal import Proposal
from app.models.review import Review
from app.models.user import User, UserStatus

__all__ = [
    "SoftDeleteMixin",
    "TimestampMixin",
    "User",
    "UserStatus",
    "Property",
    "PropertyStatus",
    "Demand",
    "DemandStatus",
    "Invitation",
    "InvitationStatus",
    "Proposal",
    "Cooperation",
    "CooperationStatus",
    "Review",
    "Device",
]
