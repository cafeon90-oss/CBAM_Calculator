"""EU CBAM 뉴스 수집 — .github/workflows/cbam_news_fetch.yml이 매월 1일 실행.

규칙
- 수동 큐레이션 항목(auto_fetched 표시 없음)은 지우지 않는다.
- 자동 수집 항목만 12개월 보존한다.
- last_updated는 항목이 실제로 늘었을 때만 바꾼다 (수집 시도 시각은 last_fetched).
- 모든 소스가 실패하면 exit 1 → Actions 실행이 실패로 표시돼 조용히 멈추지 않는다.

소스는 EU 공식 RSS 두 곳 (Commission 콘텐츠, CC BY 4.0 — 원문 링크로 출처 표시).
사이트가 요청 빈도를 제한하므로 소스당 한 번만 요청하고 재시도하지 않는다.

로컬 확인: python scripts/fetch_cbam_news.py --dry-run
"""
import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "cbam_news.json"
UA = "CBAM-Calculator-Bot/1.0 (+https://github.com/cafeon90-oss/CBAM_Calculator)"
RETENTION_DAYS = 365
TIMEOUT = 30

# TAXUD 뉴스 RSS. 주의: 이 사이트는 URL에 f[...] 필터를 붙이면 403을 준다
# (2026-05~09 수집 0건의 원인이던 news_en?f[0]=topic:39). CBAM 필터는 아래에서 직접 건다.
TAXUD_RSS_URL = "https://taxation-customs.ec.europa.eu/node/2/rss_en"
PRESS_CORNER_RSS_URL = ("https://ec.europa.eu/commission/presscorner/api/rss"
                        "?language=en&documenttype=&policyarea=&commissioner=&pagesize=50&text=CBAM")

CBAM_PATTERN = re.compile(r"\bCBAM\b|carbon border adjustment", re.IGNORECASE)
SLUG_DATE = re.compile(r"-(\d{4}-\d{2}-\d{2})_[a-z]{2}$")     # ...-2026-08-24_en


# ─────────────────────────────────────────────
# 카테고리 자동 추론 (제목 키워드 기반)
# ─────────────────────────────────────────────
def classify_category(title_en: str) -> str:
    t = title_en.lower()
    # 우선순위 순
    if any(k in t for k in ["entered into force", "goes live", "in force",
                              "first compliance", "milestone"]):
        return "milestone"
    if any(k in t for k in ["regulation", "implementing act", "delegated act",
                              "official journal", "adopted", "published"]):
        return "regulation"
    if any(k in t for k in ["proposal", "proposes", "draft"]):
        return "proposal"
    if any(k in t for k in ["agreement", "negotiation", "trilogue", "council"]):
        return "negotiation"
    if any(k in t for k in ["guidance", "default value", "benchmark", "faq",
                              "guideline", "manual"]):
        return "guidance"
    if any(k in t for k in ["reminder", "notice", "alert", "deadline"]):
        return "notice"
    return "other"


# ─────────────────────────────────────────────
# 한글 제목 자동 생성 (키워드 치환)
# 완벽하지 않아도 사용자가 가독성 ↑로 즉시 인지 가능
# ─────────────────────────────────────────────
KO_TRANSLATIONS = [
    ("CBAM", "CBAM"),
    ("Carbon Border Adjustment Mechanism", "탄소국경조정제도(CBAM)"),
    ("European Commission", "EU 집행위원회"),
    ("Commission", "EU Commission"),
    ("Council", "EU 이사회"),
    ("Parliament", "EU 의회"),
    ("Regulation", "규정"),
    ("Implementing Regulation", "시행령"),
    ("Delegated Act", "위임령"),
    ("Implementing Act", "시행법"),
    ("Official Journal", "관보(OJ)"),
    ("entered into force", "시행 발효"),
    ("enters into force", "시행 발효"),
    ("goes live", "본격 시행"),
    ("publishes", "발행"),
    ("published", "발행"),
    ("adopts", "채택"),
    ("adopted", "채택"),
    ("proposes", "제안"),
    ("proposal", "제안"),
    ("simplification", "단순화"),
    ("amendment", "개정"),
    ("guidance", "가이드"),
    ("default values", "기본값"),
    ("benchmark", "벤치마크"),
    ("transitional period", "전이기간"),
    ("definitive phase", "본격 시행 단계"),
    ("compliance", "준수"),
    ("registry", "등록부"),
    ("certificate", "인증서"),
    ("verifier", "검증인"),
    ("downstream", "후행 제품"),
    ("steel", "철강"),
    ("aluminium", "알루미늄"),
    ("aluminum", "알루미늄"),
    ("cement", "시멘트"),
    ("hydrogen", "수소"),
    ("electricity", "전력"),
    ("fertiliser", "비료"),
    ("fertilizer", "비료"),
    ("Reminder", "리마인더"),
    ("Update", "업데이트"),
    ("Notice", "공지"),
]


def generate_ko_title(title_en: str) -> str:
    """영문 제목을 한글로 부분 치환. 100% 자연스럽지는 않으나 가독성 보강."""
    ko = title_en
    # 긴 구절부터 치환 — 'Regulation'이 'Implementing Regulation'을 먼저 먹지 않도록
    for en, kr in sorted(KO_TRANSLATIONS, key=lambda pair: -len(pair[0])):
        # 단어 경계 매칭 (대소문자 무시)
        ko = re.sub(r"\b" + re.escape(en) + r"\b", kr, ko, flags=re.IGNORECASE)
    return ko


# ─────────────────────────────────────────────
# 소스 — 각 fetch 함수는 {id, date, title_en, url, source} 목록을 반환
# ─────────────────────────────────────────────
def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _rss_items(xml_bytes: bytes):
    for it in ET.fromstring(xml_bytes).iterfind("./channel/item"):
        link = (it.findtext("link") or "").strip()
        if not link.startswith("https://"):
            continue
        yield {
            "title": " ".join((it.findtext("title") or "").split()),
            "link": link,
            "description": it.findtext("description") or "",
            "pub_date": it.findtext("pubDate") or "",
        }


def _pub_date(text: str) -> str:
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError):
        return ""


def _slug(link: str) -> str:
    return link.rstrip("/").split("/")[-1]


def parse_taxud_rss(xml_bytes: bytes) -> list:
    out = []
    for it in _rss_items(xml_bytes):
        if not (CBAM_PATTERN.search(it["title"]) or CBAM_PATTERN.search(it["description"])):
            continue
        # pubDate는 '마지막 수정 시각'이라, 게시일은 링크 끝의 날짜를 우선 사용
        m = SLUG_DATE.search(it["link"])
        out.append({
            "id": re.sub(r"_[a-z]{2}$", "", _slug(it["link"])),
            "date": m.group(1) if m else _pub_date(it["pub_date"]),
            "title_en": it["title"],
            "url": it["link"],
            "source": "EU Taxation & Customs",
        })
    return out


def parse_press_corner_rss(xml_bytes: bytes) -> list:
    # 본문에만 CBAM이 스치듯 나오는 보도자료가 많아 제목으로만 거른다
    return [{
        "id": "presscorner-" + _slug(it["link"]),
        "date": _pub_date(it["pub_date"]),
        "title_en": it["title"],
        "url": it["link"],
        "source": "EU Commission Press Corner",
    } for it in _rss_items(xml_bytes) if CBAM_PATTERN.search(it["title"])]


def fetch_taxud() -> list:
    return parse_taxud_rss(http_get(TAXUD_RSS_URL))


def fetch_press_corner() -> list:
    return parse_press_corner_rss(http_get(PRESS_CORNER_RSS_URL))


SOURCES = [
    ("taxud_rss", fetch_taxud),
    ("press_corner_rss", fetch_press_corner),
]


# ─────────────────────────────────────────────
# 병합 + 보존 + 메타데이터
# ─────────────────────────────────────────────
def _date(item):
    try:
        return dt.date.fromisoformat(item.get("date", ""))
    except (TypeError, ValueError):
        return None


def to_news_item(raw: dict) -> dict:
    title_en = raw["title_en"]
    category = classify_category(title_en)
    return {
        "id": raw["id"],
        "date": raw["date"],
        "category": category,
        "importance": "high" if category in ("milestone", "regulation") else "medium",
        "important": True,
        "title_ko": generate_ko_title(title_en),
        "title_en": title_en,
        "summary_ko": (f"({title_en[:80]}{'...' if len(title_en) > 80 else ''}) — "
                       f"{raw['source']}. 원문 클릭하여 상세 확인."),
        "url": raw["url"],
        "source": raw["source"],
        "auto_fetched": True,    # 자동 수집 표식 — 이 항목만 보존기간 적용
    }


def merge_items(existing: list, fetched: list, today: dt.date):
    """(병합 결과, 새로 추가된 항목)을 반환. 수동 항목은 기간과 무관하게 유지."""
    cutoff = today - dt.timedelta(days=RETENTION_DAYS)
    seen = {it.get("id") for it in existing} | {it.get("url") for it in existing}
    added = []
    for raw in fetched:
        d = _date(raw)
        if not raw.get("id") or d is None or d < cutoff:
            continue
        if raw["id"] in seen or raw["url"] in seen:
            continue
        added.append(to_news_item(raw))
        seen.update((raw["id"], raw["url"]))

    def keep(it):
        if not it.get("auto_fetched"):
            return True
        d = _date(it)
        return d is not None and d >= cutoff

    merged = [it for it in existing + added if keep(it)]
    merged.sort(key=lambda it: it.get("date", ""), reverse=True)
    return merged, added


def update(data: dict, sources: list, today: dt.date, now: dt.datetime):
    """sources: [(이름, fetch 함수)]. (새로 추가된 항목, 성공한 소스가 있는지)를 반환."""
    fetched, fetch_log = [], []
    for name, fetch in sources:
        try:
            items = fetch()
        except Exception as e:           # 한 소스의 실패가 다른 소스를 막지 않도록
            fetch_log.append([name, f"err:{e}"])
            continue
        fetch_log.append([name, len(items)])
        fetched.extend(items)

    merged, added = merge_items(data.get("items", []), fetched, today)
    data["items"] = merged
    data["last_fetched"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    data["fetch_log"] = fetch_log
    if added:
        data["last_updated"] = today.isoformat()
    ok = any(isinstance(result, int) for _, result in fetch_log)
    return added, ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EU CBAM 뉴스 수집")
    ap.add_argument("--dry-run", action="store_true", help="파일에 쓰지 않고 결과만 출력")
    args = ap.parse_args(argv)

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)
    added, ok = update(data, SOURCES, now.date(), now)

    if not args.dry_run:
        JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"CBAM news: {len(data['items'])} items total, {len(added)} new")
    for it in added:
        print(f"  + {it['date']} [{it['source']}] {it['title_en']}")
    print(f"Fetch log: {data['fetch_log']}")
    if not ok:
        print("모든 소스 수집 실패 — fetch_log 확인", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
