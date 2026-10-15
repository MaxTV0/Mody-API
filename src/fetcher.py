import json
import requests
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://www.messisporat.com/matches/npm/"
BASE_URL = "https://www.messisporat.com"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = DATA_DIR / "today_matches.json"

STATUS_MAP = {
    "لم تبدأ": "SCHEDULED",
    "انتهت": "FINISHED",
    "تأجلت": "POSTPONED",
    "الشوط الأول": "FIRST_HALF",
    "الشوط الثاني": "SECOND_HALF",
    "نصف الوقت": "HALFTIME",
    "مباشر": "LIVE",
}


def normalize_logo(path: str) -> str:
    if not path:
        return ""
    if path.startswith("/"):
        return f"{BASE_URL}{path}"
    return path


def fetch_today_matches():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    }

    try:
        response = requests.get(SOURCE_URL, headers=headers, timeout=30)
        response.raise_for_status()
        raw = response.json()
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch matches: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON: {e}")
        return None

    raw_matches = raw.get("STING-WEB-Matches", [])
    matches = []

    for m in raw_matches:
        status_ar = m.get("Match-Status", "")
        status_en = STATUS_MAP.get(status_ar, status_ar)

        matches.append({
            "match_id": m.get("Match-id"),
            "competition": {
                "id": m.get("Cup-id"),
                "name": m.get("Cup-Name"),
                "logo": normalize_logo(m.get("Cup-Logo", "")),
            },
            "home_team": {
                "name": m.get("Team-Left", {}).get("Name"),
                "logo": normalize_logo(m.get("Team-Left", {}).get("Logo", "")),
                "color": m.get("Team-Left", {}).get("Color"),
                "score": m.get("Team-Left", {}).get("Goal"),
            },
            "away_team": {
                "name": m.get("Team-Right", {}).get("Name"),
                "logo": normalize_logo(m.get("Team-Right", {}).get("Logo", "")),
                "color": m.get("Team-Right", {}).get("Color"),
                "score": m.get("Team-Right", {}).get("Goal"),
            },
            "time": {
                "start": m.get("Time-Start"),
                "end": m.get("Time-End"),
                "current_minute": m.get("Time-Now"),
                "timezone": m.get("Time-Zone"),
            },
            "status": {
                "code": status_en,
                "text_ar": status_ar,
            },
        })

    output = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_matches": len(matches),
            "source": "messisporat.com",
        },
        "matches": matches,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[OK] Saved {len(matches)} matches to {OUTPUT_FILE}")
    return output


if __name__ == "__main__":
    fetch_today_matches()
