import uuid

from .models import ActivityLog, Commercial


def _safe_header(request, key, default=""):
    try:
        return (request.META.get(key) or default)[:255]
    except Exception:
        return default


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "unknown")[:45]


def log_activity(
    *,
    action_type,
    description,
    target_commercial=None,
    actor_commercial=None,
    request=None,
):
    """
    Centralized and resilient activity logger.
    Keeps legacy `commercial` as target, and enriches with actor/context metadata.
    """
    actor_role = "system"
    ip_address = None
    user_agent = ""
    request_path = ""
    request_method = ""
    request_id = ""

    if request is not None:
        actor_role = (request.session.get("role") or "unknown").lower()
        user_agent = _safe_header(request, "HTTP_USER_AGENT")
        request_path = (getattr(request, "path", "") or "")[:255]
        request_method = (getattr(request, "method", "") or "")[:10]
        request_id = str(uuid.uuid4())
        ip_address = _client_ip(request)

        if actor_commercial is None:
            session_cid = request.session.get("commercial_id")
            if session_cid:
                actor_commercial = Commercial.objects.filter(id=session_cid).first()

    if actor_commercial and actor_role in {"", "unknown", "system"}:
        actor_role = (getattr(actor_commercial, "role", "") or "commercial").lower()

    if target_commercial is None:
        target_commercial = actor_commercial

    ActivityLog.objects.create(
        commercial=target_commercial,
        actor_commercial=actor_commercial,
        actor_role=actor_role,
        action_type=action_type,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        request_path=request_path,
        request_method=request_method,
        request_id=request_id,
    )
