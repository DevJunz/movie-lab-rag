"""SPEC-NF2002 (PR #31 리뷰) — 다중 인스턴스, 구조 검증, 주입 날짜 · 백업 이름."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from movielab.collect.manifest import FileLock
from tests.fakes import FakeClock, make_manifest


def test_tc_nf2002_13_other_instance_reset_not_resurrected(tmp_path):
    path = tmp_path / "manifest.json"
    app = make_manifest(path)
    app.record_keyword("1", "블랙홀")
    script = make_manifest(path)
    script.reset()  # 앱이 떠 있는 동안 --reset-cache
    app.record_keyword("1", "웜홀")
    fresh = make_manifest(path)
    assert fresh.has_keyword("1", "웜홀")
    assert not fresh.has_keyword("1", "블랙홀")
    assert not app.has_keyword("1", "블랙홀")  # 읽기도 파일 변경을 반영


@pytest.mark.parametrize("content", ['{"1": []}', '{"1": {"keywords": "x"}}', "[]"])
def test_tc_nf2002_14_wrong_structure_backed_up(tmp_path, content):
    path = tmp_path / "manifest.json"
    path.write_text(content, encoding="utf-8")
    manifest = make_manifest(path)
    assert manifest.cached_queries("1", "q") is None
    manifest.record_keyword("1", "a")  # 예외 없이 동작
    assert len(list(tmp_path.glob("manifest.json.broken-*"))) == 1


def test_tc_nf2002_14_backups_do_not_collide(tmp_path):
    fixed = datetime(2026, 10, 23, 12, 0, 0)
    path = tmp_path / "manifest.json"
    for _ in range(2):
        path.write_text("{깨짐", encoding="utf-8")
        make_manifest(path, now=lambda: fixed)
    assert len(list(tmp_path.glob("manifest.json.broken-*"))) == 2


def test_tc_nf2002_14_collected_at_uses_injected_today(tmp_path):
    import json

    path = tmp_path / "manifest.json"
    make_manifest(path, today=lambda: date(2026, 1, 2)).record_keyword("1", "a")
    assert json.loads(path.read_text(encoding="utf-8"))["1"]["collected_at"] == "2026-01-02"


def test_tc_nf2002_15_change_detected_with_same_mtime_and_size(tmp_path):
    import os

    path = tmp_path / "manifest.json"
    app = make_manifest(path)
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
    import math
    import threading

    path = tmp_path / "manifest.json"

    def worker(prefix: str) -> None:
        manifest = make_manifest(path, lock_timeout_sec=math.inf)
        for n in range(40):
            manifest.record_keyword("1", f"{prefix}{n}")

    threads = [threading.Thread(target=worker, args=(p,)) for p in ("가", "나")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    fresh = make_manifest(path)
    missing = [
        f"{p}{n}" for p in ("가", "나") for n in range(40) if not fresh.has_keyword("1", f"{p}{n}")
    ]
    assert missing == []
    assert list(tmp_path.glob("*.tmp")) == []


def test_tc_nf2002_17_leftover_lock_file_does_not_block(tmp_path):
    path = tmp_path / "manifest.json"
    (tmp_path / "manifest.json.lock").write_text("", encoding="utf-8")  # 죽은 프로세스가 남긴 파일
    clock = FakeClock()
    make_manifest(path, clock=clock.monotonic, sleep=clock.sleep).record_keyword("1", "블랙홀")
    assert make_manifest(path).has_keyword("1", "블랙홀")
    assert clock.sleeps == []  # 기다리지 않았다


def test_tc_nf2002_17_lock_held_elsewhere_skips_without_blocking_reads(tmp_path, caplog):
    path = tmp_path / "manifest.json"
    make_manifest(path).record_keyword("1", "블랙홀")
    holder = FileLock(tmp_path / "manifest.json.lock", poll_sec=0.01)
    assert holder.acquire()  # 다른 프로세스가 쥐고 있는 상황
    clock = FakeClock()
    lock_free_while_waiting: list[bool] = []

    def sleep_and_check(seconds: float) -> None:
        clock.sleep(seconds)
        free = manifest._lock.acquire(
            blocking=False
        )  # 기다리는 동안 조회용 잠금은 비어 있어야 한다
        if free:
            manifest._lock.release()
        lock_free_while_waiting.append(free)

    manifest = make_manifest(
        path, lock_timeout_sec=1.0, clock=clock.monotonic, sleep=sleep_and_check
    )
    manifest.record_keyword("1", "웜홀")  # 예외 없이 건너뜀
    assert lock_free_while_waiting and all(lock_free_while_waiting)
    assert manifest.has_keyword("1", "블랙홀")
    assert not make_manifest(path).has_keyword("1", "웜홀")
    assert any("잠금" in r.getMessage() for r in caplog.records)

    holder.release()
    manifest.record_keyword("1", "웜홀")
    assert make_manifest(path).has_keyword("1", "웜홀")


def test_tc_nf2002_18_transient_read_error_retried(tmp_path, monkeypatch):
    import pathlib

    path = tmp_path / "manifest.json"
    make_manifest(path).record_keyword("1", "블랙홀")
    original = pathlib.Path.read_text
    state = {"fail": 1}

    def flaky(self, *args, **kwargs):
        if self == path and state["fail"] > 0:
            state["fail"] -= 1
            raise PermissionError("공유 위반")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", flaky)
    assert make_manifest(path).has_keyword("1", "블랙홀")
    assert list(tmp_path.glob("manifest.json.broken-*")) == []


def test_tc_nf2002_18_persistent_read_error_keeps_data(tmp_path, monkeypatch):
    import pathlib

    path = tmp_path / "manifest.json"
    app = make_manifest(path)
    app.record_keyword("1", "블랙홀")
    make_manifest(path).record_keyword("1", "웜홀")  # 파일이 바뀌어 app이 다시 읽으려 한다

    def always_fail(self, *args, **kwargs):
        raise PermissionError("공유 위반")

    monkeypatch.setattr(pathlib.Path, "read_text", always_fail)
    assert app.has_keyword("1", "블랙홀")  # 지금 내용을 유지
    app.record_keyword("1", "중력")  # 잠금 안에서 읽지 못하면 기록을 건너뛴다
    monkeypatch.undo()
    assert make_manifest(path).has_keyword("1", "웜홀")  # 남의 기록을 덮어쓰지 않았다
    assert list(tmp_path.glob("manifest.json.broken-*")) == []


def test_tc_nf2002_18_replace_permission_error_does_not_raise(tmp_path, monkeypatch):
    import os

    path = tmp_path / "manifest.json"
    manifest = make_manifest(path)

    def deny(src, dst):
        raise PermissionError("다른 프로세스가 읽는 중")

    monkeypatch.setattr(os, "replace", deny)
    manifest.record_keyword("1", "블랙홀")  # 예외 없이 경고만
    assert list(tmp_path.glob("*.tmp")) == []
    assert not manifest.has_keyword("1", "블랙홀")  # 저장 안 된 기록은 메모리에도 없다


def test_tc_nf2002_18_disk_full_does_not_raise(tmp_path, monkeypatch):
    import pathlib

    path = tmp_path / "manifest.json"
    manifest = make_manifest(path)
    original = pathlib.Path.write_text

    def full(self, *args, **kwargs):
        if self.suffix == ".tmp":
            raise OSError(28, "No space left on device")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "write_text", full)
    manifest.record_keyword("1", "블랙홀")
    assert list(tmp_path.glob("*.tmp")) == []
    assert not manifest.has_keyword("1", "블랙홀")


def test_tc_nf2002_19_non_utf8_file_backed_up(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_bytes(b"\xff\xfe\x00broken")
    manifest = make_manifest(path)  # 예외 없이 시작
    assert manifest.cached_queries("1", "q") is None
    assert len(list(tmp_path.glob("manifest.json.broken-*"))) == 1


def test_tc_nf2002_19_backup_rechecks_under_lock(tmp_path, monkeypatch):
    import json

    path = tmp_path / "manifest.json"
    path.write_text("{깨짐", encoding="utf-8")
    good = {"1": {"keywords": ["블랙홀"]}}
    original = FileLock.acquire

    def acquire_after_other_write(self, *args, **kwargs):
        path.write_text(
            json.dumps(good), encoding="utf-8"
        )  # 잠금 전에 다른 프로세스가 정상 파일을 씀
        return original(self, *args, **kwargs)

    monkeypatch.setattr(FileLock, "acquire", acquire_after_other_write)
    make_manifest(path)
    assert list(tmp_path.glob("manifest.json.broken-*")) == []
    assert json.loads(path.read_text(encoding="utf-8")) == good


# --- 세 번째 리뷰: reset 결과 · 잠금 미지원 · 백업 실패 · 반복 조회 비용 ---


def test_tc_nf2002_20_reset_reports_failure(tmp_path):
    path = tmp_path / "manifest.json"
    manifest = make_manifest(path, lock_timeout_sec=1.0)
    manifest.record_keyword("1", "블랙홀")
    holder = FileLock(tmp_path / "manifest.json.lock", poll_sec=0.01)
    assert holder.acquire()
    assert manifest.reset("1") is False
    holder.release()
    assert manifest.reset("1") is True
    assert not make_manifest(path).has_keyword("1", "블랙홀")


def test_tc_nf2002_21_unsupported_lock_gives_up_without_waiting(tmp_path, monkeypatch):
    import errno

    from movielab.collect import manifest as module

    calls = []

    def no_lock_support(fd):
        calls.append(fd)
        raise OSError(errno.ENOLCK, "No locks available")

    monkeypatch.setattr(module, "_lock_fd", no_lock_support)
    clock = FakeClock()
    lock = FileLock(tmp_path / "x.lock", poll_sec=0.01, clock=clock.monotonic, sleep=clock.sleep)
    assert lock.acquire(10.0) is False
    assert len(calls) == 1 and clock.sleeps == []


def test_tc_nf2002_21_failed_backup_does_not_overwrite(tmp_path, monkeypatch):
    import os

    path = tmp_path / "manifest.json"
    path.write_text("{깨짐", encoding="utf-8")
    original = os.replace

    def deny_backup(src, dst):
        if ".broken-" in str(dst):
            raise PermissionError("백업 실패")
        return original(src, dst)

    monkeypatch.setattr(os, "replace", deny_backup)
    make_manifest(path).record_keyword("1", "블랙홀")
    assert path.read_text(encoding="utf-8") == "{깨짐"  # 깨진 파일을 덮어쓰지 않았다


def test_tc_nf2002_21_repeated_reads_do_not_retry_same_file(tmp_path, monkeypatch):
    import pathlib

    path = tmp_path / "manifest.json"
    path.write_text("{깨짐", encoding="utf-8")
    holder = FileLock(tmp_path / "manifest.json.lock", poll_sec=0.01)
    assert holder.acquire()  # 백업용 잠금을 못 잡는 상황
    attempts = []
    original_acquire = FileLock.acquire

    def counting_acquire(self, *args, **kwargs):
        attempts.append(args)
        return original_acquire(self, *args, **kwargs)

    monkeypatch.setattr(FileLock, "acquire", counting_acquire)
    manifest = make_manifest(path)
    manifest.has_keyword("1", "a")
    manifest.has_keyword("1", "b")
    assert attempts == [(0.0,)]  # 기다리지 않고 한 번만 시도
    holder.release()

    good = tmp_path / "good.json"
    make_manifest(good).record_keyword("1", "블랙홀")
    reader = make_manifest(good)
    make_manifest(good).record_keyword("1", "웜홀")  # 파일이 바뀌어 reader가 다시 읽으려 한다
    reads = []

    def always_fail(self, *args, **kwargs):
        reads.append(self)
        raise PermissionError("공유 위반")

    monkeypatch.setattr(pathlib.Path, "read_text", always_fail)
    reader.has_keyword("1", "a")
    first = len(reads)
    reader.has_keyword("1", "b")
    assert first > 1 and len(reads) == first  # 같은 파일은 다시 시도하지 않는다
