import json
from pathlib import Path
from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "today_matches.json"


def load_data():
    if not DATA_FILE.exists():
        return {"meta": {"total_matches": 0}, "matches": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name": "MessiSporat Matches API",
        "version": "1.0.0",
        "description": "API مجاني لمباريات اليوم",
        "endpoints": {
            "/api/matches": "جميع مباريات اليوم",
            "/api/matches?competition=649": "فلترة حسب الدوري",
            "/api/matches?status=FINISHED": "المباريات المنتهية",
            "/api/competitions": "قائمة الدوريات",
            "/api/health": "فحص الحالة",
        },
    })


@app.route("/api/matches", methods=["GET"])
def get_matches():
    data = load_data()
    matches = data.get("matches", [])

    competition = request.args.get("competition")
    if competition:
        try:
            comp_id = int(competition)
            matches = [m for m in matches if m["competition"].get("id") == comp_id]
        except ValueError:
            matches = [
                m for m in matches
                if competition.lower() in (m["competition"].get("name") or "").lower()
            ]

    status = request.args.get("status")
    if status:
        matches = [m for m in matches if m["status"].get("code", "").upper() == status.upper()]

    return jsonify({
        "meta": {**data.get("meta", {}), "filtered_count": len(matches)},
        "matches": matches,
    })


@app.route("/api/competitions", methods=["GET"])
def get_competitions():
    data = load_data()
    matches = data.get("matches", [])

    competitions = {}
    for m in matches:
        comp = m.get("competition", {})
        comp_id = comp.get("id")
        if comp_id and comp_id not in competitions:
            competitions[comp_id] = {
                "id": comp_id,
                "name": comp.get("name"),
                "logo": comp.get("logo"),
                "matches_count": 0,
            }
        if comp_id:
            competitions[comp_id]["matches_count"] += 1

    return jsonify({
        "meta": data.get("meta", {}),
        "competitions": list(competitions.values()),
    })


@app.route("/api/health", methods=["GET"])
def health():
    data = load_data()
    return jsonify({
        "status": "ok",
        "last_update": data.get("meta", {}).get("generated_at"),
        "total_matches": data.get("meta", {}).get("total_matches", 0),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
