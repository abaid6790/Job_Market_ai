from flask import Blueprint, request, jsonify
from flask_login import login_required

from app.services.skills.normalizer import search_skills

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/skills/suggest")
@login_required
def suggest_skills():
    query = request.args.get("q", "")
    if len(query.strip()) < 2:
        return jsonify([])
    results = search_skills(query, limit=10)
    return jsonify(
        [{"id": s.id, "name": s.name, "category": s.category.name if s.category else None} for s in results]
    )
