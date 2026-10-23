"""SPEC-NF2002 수집 매니페스트 — 저장 · 정규화 · 깨진 파일 · 형식."""

from __future__ import annotations

import json

from tests.fakes import make_manifest


def test_tc_nf2002_06_persists_across_instances(tmp_path):
    path = tmp_path / "data" / "manifest.json"
    first = make_manifest(path)
    first.record_question("157336", "블랙홀은?", ["인터스텔라", "블랙홀"])
    first.record_keyword("157336", "블랙홀")
    first.record_page("157336", "20671", "블랙홀", chunks=12)
    first.record_item_doc("157336", "151821")
    second = make_manifest(path)
    assert second.cached_queries("157336", "블랙홀은?") == ["인터스텔라", "블랙홀"]
    assert second.has_keyword("157336", "블랙홀")
    assert second.has_page("157336", "20671")
    assert second.item_doc_page_id("157336") == "151821"
    assert not second.has_page("27205", "20671")  # 캐시는 영화별


def test_tc_nf2002_07_question_and_keyword_normalized(tmp_path):
    manifest = make_manifest(tmp_path / "m.json")
    manifest.record_question("1", "인터스텔라의 블랙홀", ["블랙홀"])
    manifest.record_keyword("1", "Black Hole")
    assert manifest.cached_queries("1", "  인터스텔라의   블랙홀 ") == ["블랙홀"]
    assert manifest.has_keyword("1", " black  hole ")
    assert manifest.cached_queries("1", "다른 질문") is None


def test_tc_nf2002_05_broken_file_backed_up(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("{깨진 json", encoding="utf-8")
    manifest = make_manifest(path)
    assert manifest.cached_queries("1", "q") is None
    backups = list(tmp_path.glob("manifest.json.broken-*"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == "{깨진 json"
    manifest.record_keyword("1", "블랙홀")
    assert json.loads(path.read_text(encoding="utf-8"))["1"]["keywords"] == ["블랙홀"]


def test_tc_nf2002_09_format_compatible_with_bundle_manifest(tmp_path):
    path = tmp_path / "manifest.json"
    manifest = make_manifest(path)
    manifest.record_keyword("157336", "웜홀")
    manifest.record_page("157336", "475498", "웜홀", chunks=7)
    manifest.record_page("157336", "99", "음반", chunks=0, rejected=True)
    entry = json.loads(path.read_text(encoding="utf-8"))["157336"]
    for key in ("keywords", "titles", "page_ids", "chunks", "collected_at", "questions"):
        assert key in entry
    assert entry["page_ids"] == ["475498"] and entry["titles"] == ["웜홀"]
    assert entry["chunks"] == 7 and entry["rejected_page_ids"] == ["99"]
    assert all(isinstance(pid, str) for pid in entry["page_ids"])


def test_tc_nf2002_reset(tmp_path):
    manifest = make_manifest(tmp_path / "m.json")
    manifest.record_keyword("1", "a")
    manifest.record_keyword("2", "b")
    manifest.reset("1")
    assert not manifest.has_keyword("1", "a") and manifest.has_keyword("2", "b")
    manifest.reset()
    assert not manifest.has_keyword("2", "b")
