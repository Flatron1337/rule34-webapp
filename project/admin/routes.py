from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from firebase_admin import firestore
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import DefaultCredentialsError

from .auth import require_admin


admin_bp = Blueprint("admin", __name__)


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


@admin_bp.route("/api/admin/health")
@require_admin
def admin_health():
    return jsonify({"ok": True})


@admin_bp.route("/api/admin/stats/overview")
@require_admin
def stats_overview():
    """
    Basic aggregated telemetry overview.

    Query params:
    - hours: window size (default 24)
    - limit: max events scanned (default 5000)
    """
    try:
        hours = int(request.args.get("hours", 24))
        limit = int(request.args.get("limit", 5000))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_query_params", "fields": ["hours", "limit"]}), 400
    hours = max(1, min(hours, 24 * 30))
    limit = max(100, min(limit, 20000))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_ms = _ms(cutoff)

    try:
        db = firestore.client()
    except DefaultCredentialsError:
        return jsonify({"error": "firebase_credentials_missing"}), 503
    except ValueError:
        return jsonify({"error": "firebase_not_initialized"}), 503
    q = (
        db.collection("telemetry_events")
        .where("ts", ">=", cutoff_ms)
        .order_by("ts")
        .limit(limit)
    )

    total = 0
    by_event = {}
    installs = set()

    try:
        for doc in q.stream():
            data = doc.to_dict() or {}
            total += 1
            name = data.get("name", "unknown")
            by_event[name] = by_event.get(name, 0) + 1
            install_id = data.get("install_id")
            if isinstance(install_id, str) and install_id:
                installs.add(install_id)
    except DefaultCredentialsError:
        return jsonify({"error": "firebase_credentials_missing"}), 503
    except ValueError:
        return jsonify({"error": "firebase_query_failed"}), 503
    except GoogleAPICallError:
        return jsonify({"error": "firebase_unavailable"}), 503

    top_events = sorted(by_event.items(), key=lambda kv: kv[1], reverse=True)[:10]

    return jsonify(
        {
            "window_hours": hours,
            "scanned_limit": limit,
            "events": total,
            "unique_installs": len(installs),
            "top_events": [{"name": k, "count": v} for k, v in top_events],
        }
    )

