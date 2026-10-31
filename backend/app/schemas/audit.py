import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: uuid.UUID | None
    actor_type: str
    actor_label: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    outcome: str
    ip_address: str | None
    user_agent: str | None
    details: dict[str, Any] | None
    created_at: datetime
