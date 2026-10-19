"""ORM models: users, documents, document chunks, tickets, approvals, audit logs.

Tables are added in Phase 1; Alembic autogenerates migrations from Base.metadata.
"""

from app.database import Base

__all__ = ["Base"]
