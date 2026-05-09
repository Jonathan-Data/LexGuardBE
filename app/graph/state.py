"""
Backward-compatibility shim.

The canonical ``AuditState`` lives in :mod:`app.models.state`. This module
re-exports it so legacy imports (``from app.graph.state import AuditState``)
continue to work without touching every call-site.
"""

from app.models.state import AuditState, SystemMetadata, new_audit_state

__all__ = ["AuditState", "SystemMetadata", "new_audit_state"]
