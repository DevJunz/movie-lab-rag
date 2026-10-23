"""SPEC-NF2002 (PR #31 리뷰) — 다중 인스턴스, 구조 검증, 주입 날짜 · 백업 이름."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from movielab.collect.manifest import Manifest


def test_tc_nf2002_13_other_instance_reset_not_resurrected(tmp_path):
    path = tmp_path / "manifest.json"
    app = Manifest(path)
    app.record_keyword("1", "블랙홀")
    script = Manifest(path)
    script.reset()  # 앱이 떠 있는 동안 --reset-cache
    app.record_keyword("1", "웜홀")
    fresh = Manifest(path)
    assert fresh.has_keyword("1", "웜홀")
    assert not fresh.has_keyword("1", "블랙홀")
    assert not app.has_keyword("1", "블랙홀")  # 읽기도 파일 변경을 반영


@pytest.mark.parametrize("content", ['{"1": []}', '{"1": {"keywords": "x"}}', "[]"])
def test_tc_nf2002_14_wrong_structure_backed_up(tmp_path, content):
    path = tmp_path / "manifest.json"
    path.write_text(content, encoding="utf-8")
    manifest = Manifest(path)
    assert manifest.cached_queries("1", "q") is None
    manifest.record_keyword("1", "a")  # 예외 없이 동작
    assert len(list(tmp_path.glob("manifest.json.broken-*"))) == 1


def test_tc_nf2002_14_backups_do_not_collide(tmp_path):
    fixed = datetime(2026, 10, 23, 12, 0, 0)
    path = tmp_path / "manifest.json"
    for _ in range(2):
        path.write_text("{깨짐", encoding="utf-8")
        Manifest(path, now=lambda: fixed)
    assert len(list(tmp_path.glob("manifest.json.broken-*"))) == 2


def test_tc_nf2002_14_collected_at_uses_injected_today(tmp_path):
    import json

    path = tmp_path / "manifest.json"
    Manifest(path, today=lambda: date(2026, 1, 2)).record_keyword("1", "a")
    assert json.loads(path.read_text(encoding="utf-8"))["1"]["collected_at"] == "2026-01-02"


def test_tc_nf2002_15_change_detected_with_same_mtime_and_size(tmp_path):
    import os

    path = tmp_path / "manifest.json"
    app = Manifest(path)
    app.record_keyword("1", "블랙홀")
    before = path.stat()
    other = tmp_path / "other.tmp"  # 다른 프로세스의 쓰기: 같은 크기 내용을 새 파일로 바꿔 넣는다
    other.write_bytes(path.read_bytes().replace("블랙홀".encode(), "웜홀가".encode()))
    os.replace(other, path)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))  # 같은 타이머 틱 재현
    assert path.stat().st_size == before.st_size
    assert app.has_keyword("1", "웜홀가")
    assert not app.has_keyword("1", "블랙홀")


def test_tc_nf2002_16_concurrent_instances_lose_no_records(tmp_path):
    import threading

    path = tmp_path / "manifest.json"

    def worker(prefix: str) -> None:
        manifest = Manifest(path)
        for n in range(40):
            manifest.record_keyword("1", f"{prefix}{n}")

    threads = [threading.Thread(target=worker, args=(p,)) for p in ("가", "나")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    fresh = Manifest(path)
    missing = [
        f"{p}{n}" for p in ("가", "나") for n in range(40) if not fresh.has_keyword("1", f"{p}{n}")
    ]
    assert missing == []
    assert not (tmp_path / "manifest.json.lock").exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_tc_nf2002_17_stale_lock_removed(tmp_path):
    import os
    import time

    path = tmp_path / "manifest.json"
    lock = tmp_path / "manifest.json.lock"
    lock.write_text("", encoding="utf-8")
    old = time.time() - 3600
    os.utime(lock, (old, old))
    Manifest(path).record_keyword("1", "블랙홀")
    assert Manifest(path).has_keyword("1", "블랙홀")
    assert not lock.exists()


def test_tc_nf2002_17_lock_timeout_skips_record(tmp_path, caplog):
    path = tmp_path / "manifest.json"
    lock = tmp_path / "manifest.json.lock"
    lock.write_text("", encoding="utf-8")  # 다른 프로세스가 잡고 있는 새 잠금
    manifest = Manifest(path, lock_timeout_sec=0.05, sleep=lambda s: None)
    manifest.record_keyword("1", "블랙홀")  # 예외 없이 건너뜀
    assert not Manifest(path).has_keyword("1", "블랙홀")
    assert lock.exists()  # 남의 잠금은 지우지 않는다
    assert any("잠금" in r.getMessage() for r in caplog.records)


def test_tc_nf2002_18_transient_read_error_retried(tmp_path, monkeypatch):
    import pathlib

    path = tmp_path / "manifest.json"
    Manifest(path).record_keyword("1", "블랙홀")
    original = pathlib.Path.read_text
    state = {"fail": 1}

    def flaky(self, *args, **kwargs):
        if self == path and state["fail"] > 0:
            state["fail"] -= 1
            raise PermissionError("공유 위반")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", flaky)
    assert Manifest(path, sleep=lambda s: None).has_keyword("1", "블랙홀")
    assert list(tmp_path.glob("manifest.json.broken-*")) == []


def test_tc_nf2002_18_persistent_read_error_keeps_data(tmp_path, monkeypatch):
    import pathlib

    path = tmp_path / "manifest.json"
    app = Manifest(path, sleep=lambda s: None)
    app.record_keyword("1", "블랙홀")
    Manifest(path).record_keyword("1", "웜홀")  # 파일이 바뀌어 app이 다시 읽으려 한다

    def always_fail(self, *args, **kwargs):
        raise PermissionError("공유 위반")

    monkeypatch.setattr(pathlib.Path, "read_text", always_fail)
    assert app.has_keyword("1", "블랙홀")  # 지금 내용을 유지
    assert list(tmp_path.glob("manifest.json.broken-*")) == []
    assert path.exists()


def test_tc_nf2002_18_replace_permission_error_does_not_raise(tmp_path, monkeypatch):
    import os

    path = tmp_path / "manifest.json"
    manifest = Manifest(path, sleep=lambda s: None)

    def deny(src, dst):
        raise PermissionError("다른 프로세스가 읽는 중")

    monkeypatch.setattr(os, "replace", deny)
    manifest.record_keyword("1", "블랙홀")  # 예외 없이 경고만
    assert list(tmp_path.glob("*.tmp")) == []
    assert not (tmp_path / "manifest.json.lock").exists()
