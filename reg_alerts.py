"""
reg_alerts.py
=============

자매 도구 reg_tracker(규제·방법론 개정 추적기)의 알림 피드를 읽는다.

- 피드: reg_tracker repo의 feed/alerts.json (형식: feed/SCHEMA.md)
- 이 도구의 몫: targets[].repo 가 "CBAM_Calculator" 인 알림
- 이미 반영한 알림: data/reg_ack.json 에 id를 적어 두면 화면에서 빠진다

피드를 못 받아도 계산기는 그대로 동작해야 하므로, 실패하면 조용히 None을 돌려준다.
"""

import json
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

REG_FEED_URL = (
    "https://raw.githubusercontent.com/cafeon90-oss/"
    "reg_tracker/main/feed/alerts.json"
)
REG_TRACKER_URL = "https://github.com/cafeon90-oss/reg_tracker"
REPO_NAME = "CBAM_Calculator"
SUPPORTED_SCHEMA = 1
ACK_PATH = Path(__file__).parent / "data" / "reg_ack.json"


@st.cache_data(ttl=21600)  # 6시간 캐시
def fetch_feed(url: str = REG_FEED_URL) -> Optional[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def load_ack(path: Path = ACK_PATH) -> set:
    """확인 완료한 알림 id 집합. 파일이 없거나 깨져 있으면 빈 집합."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {a["id"] for a in data.get("acknowledged", [])}
    except Exception:
        return set()


def pending_alerts(feed: Optional[Dict[str, Any]], ack: set, repo: str = REPO_NAME) -> List[Dict[str, Any]]:
    """이 도구에 해당하고 아직 확인하지 않은 알림. 중요도 높은 순, 같은 중요도는 최신순."""
    if not feed or feed.get("schema_version") != SUPPORTED_SCHEMA:
        return []
    out = []
    for alert in feed.get("alerts", []):
        mine = [t for t in alert.get("targets", []) if t.get("repo") == repo]
        if mine and alert.get("id") not in ack:
            out.append({**alert, "targets": mine})
    rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda a: a.get("detected", ""), reverse=True)
    out.sort(key=lambda a: rank.get(a.get("importance"), 3))
    return out


def acknowledged_count(feed: Optional[Dict[str, Any]], ack: set, repo: str = REPO_NAME) -> int:
    if not feed or feed.get("schema_version") != SUPPORTED_SCHEMA:
        return 0
    return sum(1 for a in feed.get("alerts", [])
               if a.get("id") in ack and any(t.get("repo") == repo for t in a.get("targets", [])))
