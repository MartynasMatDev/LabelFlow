from .models import ActivityLog


def log_activity(project, user, action: str, detail: str = '', meta: dict | None = None):
    """Create an ActivityLog entry.  Never raises — failures are silent."""
    try:
        ActivityLog.objects.create(
            project=project,
            user=user,
            action=action,
            detail=detail,
            meta=meta or {},
        )
    except Exception:
        pass  # logging must never break the main flow
