import json
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

# ============ الإعدادات ============
API_BASE = "https://www.messisporat.com/matches/npm/"
API_ORIGIN = "https://www.messisporat.com"
LANG = 27  # 27 = العربية

# النطاق الافتراضي: من 30 يوماً مضت حتى اليوم
DEFAULT_DAYS_BACK = 30

# مسارات الحفظ
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_DIR = DATA_DIR / "daily"
DATA_DIR.mkdir(exist_ok=True)
DAILY_DIR.mkdir(exist_ok=True)

TODAY_FILE = DATA_DIR / "today_matches.json"
INDEX_FILE = DATA_DIR / "index.json"
ALL_FILE = DATA_DIR / "all_matches.json"


# ============ ترجمة حالات المباريات ============
STATUS_MAP = {
    "لم تبدأ": "SCHEDULED",
    "انتهت": "FINISHED",
    "تأجلت": "POSTPONED",
    "الشوط الأول": "FIRST_HALF",
    "الشوط الثاني": "SECOND_HALF",
    "نصف الوقت": "HALFTIME",
    "مباشر": "LIVE",
}


# ============ دوال مساعدة ============
def normalize_logo(path: str) -> str:
    """تحويل مسار الشعار النسبي إلى رابط كامل"""
    if not path:
        return ""
    if path.startswith("http"):
        return path
    if path.startswith("/"):
        return f"{API_ORIGIN}{path}"
    return f"{API_ORIGIN}/{path}"


def get_timezone_offset() -> str:
    """إرجاع فرق التوقيت الحالي بصيغة +HH:MM"""
    offset = -datetime.now().astimezone().utcoffset().total_seconds() // 60
    offset = int(offset)
    sign = "+" if offset >= 0 else "-"
    offset = abs(offset)
    return f"{sign}{offset // 60:02d}:{offset % 60:02d}"


def fetch_with_fallback(url: str, max_retries: int = 3):
    """جلب البيانات مع إعادة المحاولة"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Referer": f"{API_ORIGIN}/",
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            last_error = e
            print(f"[WARN] Attempt {attempt + 1}/{max_retries} failed: {e}")

    print(f"[ERROR] All attempts failed: {last_error}")
    return None


# ============ جلب المباريات ============
def fetch_matches_for_date(date_str: str):
    """جلب مباريات يوم محدد"""
    tz = get_timezone_offset()
    url = f"{API_BASE}?date={date_str}&lang={LANG}&time={requests.utils.quote(tz)}"

    print(f"[INFO] Fetching: {date_str}")
    json_text = fetch_with_fallback(url)
    if not json_text:
        return None

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON for {date_str}: {e}")
        return None

    raw_matches = data.get("STING-WEB-Matches", [])
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

    return matches


# ============ حفظ البيانات ============
def save_daily(date_str: str, matches: list, meta: dict):
    """حفظ ملف يوم واحد"""
    data = {
        "meta": {
            "date": date_str,
            "total_matches": len(matches),
            **meta,
        },
        "matches": matches,
    }

    daily_file = DAILY_DIR / f"{date_str}.json"
    with open(daily_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] daily/{date_str}.json: {len(matches)} matches")
    return data


def update_index_and_all():
    """يبني index.json و all_matches.json من كل ملفات daily"""
    days = []
    all_days_data = []

    # ترتيب تصاعدي حسب اسم الملف (أي حسب التاريخ)
    for f in sorted(DAILY_DIR.glob("*.json")):
        date_str = f.stem
        try:
            with open(f, "r", encoding="utf-8") as fh:
                content = json.load(fh)
            meta = content.get("meta", {})
            days.append({
                "date": date_str,
                "total_matches": meta.get("total_matches", 0),
                "url": f"https://raw.githubusercontent.com/MaxTV0/Mody-API/main/data/daily/{date_str}.json",
            })
            all_days_data.append({
                "date": date_str,
                "matches": content.get("matches", []),
            })
        except Exception as e:
            print(f"[WARN] Skipped {f}: {e}")

    # ترتيب عكسي (الأحدث أولاً)
    days = list(reversed(days))
    all_days_data = list(reversed(all_days_data))

    total_matches = sum(d["total_matches"] for d in days)

    # index.json
    index_data = {
        "meta": {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_days": len(days),
            "total_matches_all_days": total_matches,
            "oldest_date": days[-1]["date"] if days else None,
            "newest_date": days[0]["date"] if days else None,
        },
        "days": days,
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    print(f"[OK] index.json: {len(days)} days, {total_matches} matches")

    # all_matches.json
    all_data = {
        "meta": {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_days": len(days),
            "total_matches": total_matches,
            "oldest_date": days[-1]["date"] if days else None,
            "newest_date": days[0]["date"] if days else None,
        },
        "days": all_days_data,
    }
    with open(ALL_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"[OK] all_matches.json: {total_matches} matches across {len(days)} days")


# ============ الدالة الرئيسية ============
def main():
    """جلب المباريات لليوم وكل الأيام السابقة المطلوبة"""
    now = datetime.now(timezone.utc)
    today = now.date()

    # قراءة عدد الأيام من سطر الأوامر (اختياري)
    days_back = DEFAULT_DAYS_BACK
    if len(sys.argv) > 1:
        try:
            days_back = int(sys.argv[1])
        except ValueError:
            pass

    print(f"[START] Fetching matches for {days_back} days back from {today}")

    fetched_count = 0
    for i in range(days_back + 1):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")

        # إذا كان الملف موجوداً، تخطاه (إلا لليوم الحالي)
        daily_file = DAILY_DIR / f"{date_str}.json"
        if daily_file.exists() and date != today:
            print(f"[SKIP] {date_str} already exists")
            continue

        matches = fetch_matches_for_date(date_str)
        if matches is not None:
            meta = {
                "generated_at": now.isoformat(),
                "source": "messisporat.com",
                "timezone": get_timezone_offset(),
            }
            save_daily(date_str, matches, meta)
            fetched_count += 1

        # حفظ ملف اليوم بشكل منفصل
        if date == today:
            today_data = {
                "meta": {
                    "generated_at": now.isoformat(),
                    "date": date_str,
                    "total_matches": len(matches),
                    "source": "messisporat.com",
                },
                "matches": matches,
            }
            with open(TODAY_FILE, "w", encoding="utf-8") as f:
                json.dump(today_data, f, ensure_ascii=False, indent=2)
            print(f"[OK] today_matches.json: {len(matches)} matches")

    print(f"[DONE] Fetched {fetched_count} new days")
    update_index_and_all()


if __name__ == "__main__":
    main()
