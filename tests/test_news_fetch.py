"""scripts/fetch_cbam_news.py — RSS 파싱·보존 규칙·갱신일·실패 감지 테스트 (네트워크 없음)."""
import datetime as dt
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "fetch_cbam_news.py"
TODAY = dt.date(2026, 10, 1)
NOW = dt.datetime(2026, 10, 1, 0, 0, tzinfo=dt.timezone.utc)

TAXUD_RSS = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>News</title>
<item>
  <title>The European Commission publishes guidance for CBAM verifiers</title>
  <link>https://taxation-customs.ec.europa.eu/news/commission-publishes-guidance-cbam-verifiers-2026-08-24_en</link>
  <description>&lt;p&gt;Guidance for accreditation bodies&lt;/p&gt;</description>
  <pubDate>Tue, 25 Aug 2026 10:00:00 +0200</pubDate>
</item>
<item>
  <title>New VAT rates published</title>
  <link>https://taxation-customs.ec.europa.eu/news/new-vat-rates-2026-08-20_en</link>
  <description>VAT only</description>
  <pubDate>Thu, 20 Aug 2026 10:00:00 +0200</pubDate>
</item>
<item>
  <title>Webinar follow-up: accreditation and verification</title>
  <link>https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/webinar-follow-up-2026-05-07_en</link>
  <description>About the Carbon Border Adjustment Mechanism verifiers</description>
  <pubDate>Fri, 08 May 2026 09:00:00 +0200</pubDate>
</item>
</channel></rss>"""

PRESS_CORNER_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
  <title>Commission strengthens the Carbon Border Adjustment Mechanism</title>
  <link>https://ec.europa.eu/commission/presscorner/detail/en/ip_25_3088</link>
  <description>Press release</description>
  <pubDate>Tue, 16 Dec 2025 11:00:00 GMT</pubDate>
</item>
<item>
  <title>Electrification Action Plan</title>
  <link>https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1596</link>
  <description>Mentions CBAM in passing</description>
  <pubDate>Thu, 16 Jul 2026 10:00:00 GMT</pubDate>
</item>
<item>
  <title>CBAM item with an unsafe link</title>
  <link>javascript:alert(1)</link>
  <pubDate>Thu, 16 Jul 2026 10:00:00 GMT</pubDate>
</item>
</channel></rss>"""


@pytest.fixture(scope="module")
def news():
    spec = importlib.util.spec_from_file_location("fetch_cbam_news", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manual(id_, date):
    return {"id": id_, "date": date, "title_ko": id_, "url": f"https://example.org/{id_}"}


def _raw(id_, date, title="CBAM implementing regulation adopted by the Commission"):
    return {"id": id_, "date": date, "title_en": title,
            "url": f"https://example.org/{id_}", "source": "Test"}


def _data():
    return {"last_updated": "2026-09-15", "items": [_manual("known", "2026-01-14")]}


# ── RSS 파싱 ─────────────────────────────────────────────────────────
def test_taxud_rss_keeps_cbam_items_and_dates_from_link(news):
    items = news.parse_taxud_rss(TAXUD_RSS)
    assert [(it["id"], it["date"]) for it in items] == [
        ("commission-publishes-guidance-cbam-verifiers-2026-08-24", "2026-08-24"),  # pubDate(8/25) 아닌 링크 날짜
        ("webinar-follow-up-2026-05-07", "2026-05-07"),                            # 설명에만 CBAM 언급
    ]
    assert items[0]["source"] == "EU Taxation & Customs"


def test_press_corner_rss_filters_on_title_and_https(news):
    items = news.parse_press_corner_rss(PRESS_CORNER_RSS)
    assert [(it["id"], it["date"]) for it in items] == [("presscorner-ip_25_3088", "2025-12-16")]


def test_ko_title_replaces_longer_phrases_first(news):
    assert (news.generate_ko_title("The European Commission adopts Implementing Regulation")
            == "The EU 집행위원회 채택 시행령")


# ── 병합·보존 ────────────────────────────────────────────────────────
def test_manual_items_survive_retention(news):
    merged, added = news.merge_items([_manual("old-manual", "2024-01-01")], [], TODAY)
    assert [it["id"] for it in merged] == ["old-manual"]
    assert added == []


def test_only_old_auto_items_are_pruned(news):
    existing = [
        {**_manual("old-auto", "2025-09-01"), "auto_fetched": True},
        {**_manual("recent-auto", "2026-06-01"), "auto_fetched": True},
    ]
    merged, _ = news.merge_items(existing, [], TODAY)
    assert [it["id"] for it in merged] == ["recent-auto"]


def test_new_items_are_added_once_and_marked(news):
    fetched = [_raw("known", "2026-01-14"), _raw("new", "2026-09-20"),
               _raw("new", "2026-09-20"), _raw("too-old", "2025-01-01")]
    merged, added = news.merge_items(_data()["items"], fetched, TODAY)
    assert [it["id"] for it in added] == ["new"]
    assert added[0]["auto_fetched"] is True
    assert added[0]["category"] == "regulation"
    assert [it["id"] for it in merged] == ["new", "known"]     # 최신순


# ── 메타데이터·실패 감지 ─────────────────────────────────────────────
def test_last_updated_kept_when_nothing_new(news):
    data = _data()
    added, ok = news.update(data, [("empty", lambda: [])], TODAY, NOW)
    assert (added, ok) == ([], True)
    assert data["last_updated"] == "2026-09-15"
    assert data["last_fetched"] == "2026-10-01T00:00:00Z"
    assert data["fetch_log"] == [["empty", 0]]


def test_last_updated_moves_when_items_added(news):
    data = _data()
    added, ok = news.update(data, [("src", lambda: [_raw("new", "2026-09-20")])], TODAY, NOW)
    assert (len(added), ok) == (1, True)
    assert data["last_updated"] == "2026-10-01"


def test_all_sources_failing_is_reported(news):
    def blocked():
        raise OSError("HTTP Error 403: Forbidden")

    data = _data()
    added, ok = news.update(data, [("a", blocked), ("b", blocked)], TODAY, NOW)
    assert (added, ok) == ([], False)
    assert data["items"] == _data()["items"]                    # 아무것도 지우지 않음
    assert data["fetch_log"][0] == ["a", "err:HTTP Error 403: Forbidden"]
