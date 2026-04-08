from flask import Blueprint, current_app, jsonify

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/health")
def admin_health():
    return jsonify(
        ok=True,
        firebase_admin_ready=bool(current_app.config.get("FIREBASE_ADMIN_READY")),
    )

