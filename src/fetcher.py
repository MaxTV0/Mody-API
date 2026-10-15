import json
import requests
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://phantom-pro-theme.malik-web.net/inc/modules/loaders/PX01MA/"
API_ORIGIN = "https://phantom-pro-theme.malik-web.net"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_DIR = DATA_DIR / "daily"
DATA_DIR.mkdir(exist_ok=True)
DAILY_DIR.mkdir(exist_ok=True)

TODAY_FILE = DATA_DIR / "today_matches.json"
INDEX_FILE = DATA_DIR / "index.json"


def normalize_logo(path: str) -> str:
    """تحويل المسار النسبي إلى رابط كامل"""
    if not path:
        return ""
    if path.startswith("http"):
        return path
    if path.startswith("/"):
        return f"{API_ORIGIN}{path}"
    return f"{API_ORIGIN}/{path}"


def fetch_today_matches():
    """جلب مباريات اليوم من phantom-pro-theme"""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Referer": f"{API_ORIGIN}/",
    }

    try:
        response = requests.get(API_BASE, headers=headers, timeout=30)
        response.raise_for_status()
        raw = response.json()
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON: {e}")
        return None

    raw_competitions = raw.get("competitions", [])
    matches = []

    for comp in raw_competitions:
        comp_id = comp.get("id")
        comp_name = comp.get("competition_name")
        comp_logo = normalize_logo(comp.get("competition_img", ""))

        for m in comp.get("matches", []):
            matches.append({
                "match_id": m.get("match_id"),
                "competition": {
                    "id": comp_id,
                    "name": comp_name,
                    "logo": comp_logo,
                    "url_name": comp.get("competition_url_name"),
                    "has_standings": comp.get("has_standings", False),
                },
                "home_team": {
                    "name": m.get("team1_name"),
                    "url_name": m.get("team1_url_name"),
                    "logo": normalize_logo(m.get("team1_img", "")),
                    "score": m.get("team1_score"),
                    "is_winner": m.get("home_is_winner", False),
                },
                "away_team": {
                    "name": m.get("team2_name"),
                    "url_name": m.get("team2_url_name"),
                    "logo": normalize_logo(m.get("team2_img", "")),
                    "score": m.get("team2_score"),
                    "is_winner": m.get("away_is_winner", False),
                },
                "time": {
                    "start": m.get("match_time"),
                    "start_timestamp": m.get("start_timestamp"),
                    "estimated_end_timestamp": m.get("estimated_end_timestamp"),
                    "current_minute": m.get("current_minute"),
                    "countdown_seconds": m.get("countdown_seconds"),
                },
                "status": {
                    "code": m.get("status_class", "").upper(),
                    "text_ar": m.get("match_status"),
                    "phase": m.get("phase"),
                    "progress_percentage": m.get("progress_percentage", 0),
                },
                "penalty": {
                    "home": m.get("penalty_home", 0),
                    "away": m.get("penalty_away", 0),
                    "home_map": m.get("penalty_home_map", []),
                    "away_map": m.get("penalty_away_map", []),
                },
                "has_lineups": m.get("has_lineups", False),
            })

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    generated_at = now.isoformat()

    output = {
        "meta": {
            "generated_at": generated_at,
            "date": today_str,
            "total_matches": len(matches),
            "total_competitions": len(raw_competitions),
            "has_live_matches": raw.get("hasLiveMatches", False),
            "source": "phantom-pro-theme.malik-web.net",
        },
        "matches": matches,
    }

    # 1. ملف اليوم
    with open(TODAY_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] Today file: {len(matches)} matches")

    # 2. أرشيف اليوم
    daily_file = DAILY_DIR / f"{today_str}.json"
    with open(daily_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] Daily archive: {daily_file}")

    # 3. تحديث الفهرس
    update_index()

    return output


def update_index():
    """يبني فهرساً بكل الأيام المتاحة"""
    days = []
    for f in sorted(DAILY_DIR.glob("*.json"), reverse=True):
        date_str = f.stem
        try:
            with open(f, "r", encoding="utf-8") as fh:
                content = json.load(fh)
            days.append({
                "date": date_str,
                "total_matches": content.get("meta", {}).get("total_matches", 0),
                "generated_at": content.get("meta", {}).get("generated_at"),
                "url": f"https://raw.githubusercontent.com/MaxTV0/Mody-API/main/data/daily/{date_str}.json",
            })
        except Exception as e:
            print(f"[WARN] Skipped {f}: {e}")
            continue

    index_data = {
        "meta": {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_days": len(days),
            "oldest_date": days[-1]["date"] if days else None,
            "newest_date": days[0]["date"] if days else None,
        },
        "days": days,
    }

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    print(f"[OK] Index: {len(days)} days")


if __name__ == "__main__":
    fetch_today_matches()
