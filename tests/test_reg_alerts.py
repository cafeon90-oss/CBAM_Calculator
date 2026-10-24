"""reg_alerts.py — reg_tracker 피드에서 이 계산기 몫만 고르고 확인 완료를 걸러 내는지 (네트워크 없음)."""
import json

import reg_alerts as ra


def _feed(*alerts, version=1):
    return {"schema_version": version, "alerts": list(alerts)}


def _alert(aid, importance="high", repos=("CBAM_Calculator",), detected="2026-10-25"):
    return {"id": aid, "importance": importance, "detected": detected, "title": aid,
            "targets": [{"repo": r, "path": "see_steel.py", "symbol": "X"} for r in repos]}


def test_only_this_repo_and_unacknowledged():
    feed = _feed(_alert("eu:A"), _alert("eu:B", repos=("carbon_screener",)), _alert("eu:C"))
    got = ra.pending_alerts(feed, ack={"eu:C"})
    assert [a["id"] for a in got] == ["eu:A"]


def test_other_repo_targets_are_dropped_from_alert():
    feed = _feed(_alert("eu:A", repos=("CBAM_Calculator", "carbon_screener")))
    (a,) = ra.pending_alerts(feed, ack=set())
    assert [t["repo"] for t in a["targets"]] == ["CBAM_Calculator"]


def test_sorted_by_importance_then_newest():
    feed = _feed(_alert("low", "low", detected="2026-10-30"), _alert("old", "high", detected="2026-09-01"),
                 _alert("new", "high", detected="2026-10-20"))
    assert [a["id"] for a in ra.pending_alerts(feed, ack=set())] == ["new", "old", "low"]


def test_missing_or_unknown_schema_is_silent():
    assert ra.pending_alerts(None, ack=set()) == []
    assert ra.pending_alerts(_feed(_alert("eu:A"), version=2), ack=set()) == []
    assert ra.acknowledged_count(None, set()) == 0


def test_load_ack_tolerates_missing_and_broken_files(tmp_path):
    assert ra.load_ack(tmp_path / "none.json") == set()
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert ra.load_ack(bad) == set()
    good = tmp_path / "ack.json"
    good.write_text(json.dumps({"acknowledged": [{"id": "eu:A"}]}), encoding="utf-8")
    assert ra.load_ack(good) == {"eu:A"}


def test_shipped_ack_covers_ir_2026_1740():
    # 헤더에 'IR 2026/1740 정정 반영'이라고 적었으므로 이 알림은 확인 완료여야 한다
    assert "eu:32026R1740" in ra.load_ack()
