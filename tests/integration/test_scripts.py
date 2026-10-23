"""실행 스크립트 통합 테스트."""

from __future__ import annotations

import json

import pytest

from scripts import index_meta


def test_tc_f2001_10_show_prints_index_text(tmp_settings, monkeypatch, capsys):
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    assert index_meta.main(["--show", "157336"]) == 0
    out = capsys.readouterr().out
    assert "제목: 인터스텔라 (2014)" in out
    assert "감독: 크리스토퍼 놀란" in out
    labels = [line.split(":")[0] for line in out.splitlines()]
    assert labels == ["제목", "원제", "장르", "감독", "출연", "제작 국가", "원어", "줄거리"]


def test_tc_f2001_10_show_unknown_id(tmp_settings, monkeypatch, capsys):
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    assert index_meta.main(["--show", "999999999"]) == 1
    assert "찾을 수 없" in capsys.readouterr().out


def test_tc_f2001_10_missing_data_file(tmp_settings, tmp_path, monkeypatch, capsys):
    raw = dict(tmp_settings.raw)
    raw["paths"] = {**raw["paths"], "movies": str(tmp_path / "없음.json")}
    path = tmp_path / "missing.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(path))
    assert index_meta.main(["--show", "157336"]) == 1
    out = capsys.readouterr().out
    assert "데이터" in out and "Traceback" not in out


def _settings_with_movies(tmp_settings, tmp_path, content: str):
    movies = tmp_path / "movies_bad.json"
    movies.write_text(content, encoding="utf-8")
    raw = dict(tmp_settings.raw)
    raw["paths"] = {**raw["paths"], "movies": str(movies)}
    path = tmp_path / "settings_bad.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize("content", ["[{깨진", '{"movie_id": "1"}'])
def test_tc_f2001_12_bad_data_file_no_traceback(
    tmp_settings, tmp_path, monkeypatch, capsys, content
):
    path = _settings_with_movies(tmp_settings, tmp_path, content)
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(path))
    assert index_meta.main(["--show", "157336"]) == 1
    out = capsys.readouterr().out
    assert "형식" in out and "Traceback" not in out


def test_tc_f2001_12_bad_settings_file_no_traceback(tmp_path, monkeypatch, capsys):
    broken = tmp_path / "broken_settings.json"
    broken.write_text("{설정 아님", encoding="utf-8")
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(broken))
    assert index_meta.main(["--show", "157336"]) == 1
    out = capsys.readouterr().out
    assert "설정" in out and "Traceback" not in out


# --- SPEC-F2002 색인 · 건수 · 재색인 ---


def _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path, embeddings=None, **indexing):
    """스크립트가 가짜 임베딩과 (필요하면 indexing 값을 바꾼) 임시 설정을 쓰게 한다."""
    from movielab.container import build_services
    from tests.fakes import FakeEmbeddings

    raw = json.loads(json.dumps(tmp_settings.raw))
    raw["indexing"].update(indexing)
    path = tmp_path / "settings_index.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(path))
    emb = embeddings or FakeEmbeddings()
    monkeypatch.setattr(
        index_meta, "build_services", lambda settings: build_services(settings, embeddings=emb)
    )
    return emb


def test_tc_f2002_05_index_count_and_rebuild(tmp_settings, tmp_path, monkeypatch, capsys):
    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path)
    assert index_meta.main([]) == 0
    assert "로드 12건 / 색인 12건 / 건너뜀 0건" in capsys.readouterr().out
    assert index_meta.main([]) == 0  # 재실행 안전
    assert "색인 12건" in capsys.readouterr().out
    assert index_meta.main(["--count"]) == 0
    assert "movie_meta: 12" in capsys.readouterr().out
    assert index_meta.main(["--rebuild"]) == 0
    assert "색인 12건" in capsys.readouterr().out


def test_tc_f2002_06_failed_batch_exit_code(tmp_settings, tmp_path, monkeypatch, capsys):
    from tests.fakes import FakeEmbeddings

    broken = FakeEmbeddings(fail_when=lambda texts: any("인셉션" in t for t in texts))
    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path, broken, retry_wait_sec=0)
    assert index_meta.main(["--batch-size", "5"]) == 1
    out = capsys.readouterr().out
    assert "실패한 배치" in out and "Traceback" not in out


def test_tc_f2002_10_count_without_key(tmp_settings, monkeypatch, capsys):
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    assert index_meta.main(["--count"]) == 0
    assert "movie_meta: 0" in capsys.readouterr().out


def test_tc_f2002_11_no_key_keeps_existing_index(tmp_settings, tmp_path, monkeypatch, capsys):
    from movielab.container import build_services

    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path)
    assert index_meta.main([]) == 0
    capsys.readouterr()
    # 이제 키도 임베딩 주입도 없는 상태로 색인 · 재색인
    monkeypatch.setattr(index_meta, "build_services", lambda settings: build_services(settings))
    for argv in ([], ["--rebuild"]):
        assert index_meta.main(argv) == 1
        out = capsys.readouterr().out
        assert "GMS_API_KEY" in out and "Traceback" not in out
    assert index_meta.main(["--count"]) == 0
    assert "movie_meta: 12" in capsys.readouterr().out  # 기존 색인 유지


@pytest.mark.parametrize("value", ["0", "-5", "abc"])
def test_tc_f2002_14_batch_size_must_be_positive(tmp_settings, monkeypatch, value):
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    with pytest.raises(SystemExit) as exit_info:
        index_meta.main(["--batch-size", value])
    assert exit_info.value.code == 2


def test_tc_f2002_11_invalid_key_message_and_index_kept(
    tmp_settings, tmp_path, monkeypatch, capsys
):
    import httpx
    import openai

    from tests.fakes import FakeEmbeddings

    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path)
    assert index_meta.main([]) == 0
    capsys.readouterr()

    def auth_error():
        request = httpx.Request("POST", "https://gms.example.invalid/v1/embeddings")
        return openai.AuthenticationError(
            "bad", response=httpx.Response(401, request=request), body=None
        )

    bad = FakeEmbeddings(fail_when=lambda texts: True, error=auth_error)
    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path, bad)
    assert index_meta.main(["--rebuild"]) == 1
    out = capsys.readouterr().out
    assert "올바르지 않" in out and "잠시 후" not in out and "Traceback" not in out
    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path)
    assert index_meta.main(["--count"]) == 0
    assert "movie_meta: 12" in capsys.readouterr().out


# --- SPEC-F2004 수집 스크립트 ---


def test_tc_f2004_15_collect_script_reports_selection(tmp_settings, monkeypatch, capsys):
    from movielab.container import build_services
    from scripts import collect
    from tests.fakes import FakeChatModel, FakeEmbeddings, pick_titles

    llm = FakeChatModel(rules={"검색어 추출": '["블랙홀"]', "후보 선별": pick_titles("블랙홀")})
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    monkeypatch.setattr(
        collect, "build_services", lambda s: build_services(s, llm=llm, embeddings=FakeEmbeddings())
    )
    code = collect.main(["--movie-id", "157336", "--question", "블랙홀은?", "--source", "bundle"])
    out = capsys.readouterr().out
    assert code == 0
    assert "소스: bundle" in out
    assert "검색어:" in out and "블랙홀" in out
    assert "수집 문서" in out and "인터스텔라 (항목 자체 문서)" in out
    assert "버린 문서" in out and "p2_not_selected" in out


def test_tc_f2004_15_collect_script_unknown_movie(tmp_settings, monkeypatch, capsys):
    from scripts import collect

    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    assert collect.main(["--movie-id", "0", "--question", "q"]) == 1
    assert "찾을 수 없" in capsys.readouterr().out


# --- SPEC-F2005 재색인 스크립트 ---


def test_tc_f2005_09_reindex_docs_reports_counts(tmp_settings, monkeypatch, capsys):
    import dataclasses

    from movielab.container import build_services
    from scripts import reindex_docs
    from tests.fakes import FakeEmbeddings
    from tests.fakes.source import make_doc

    emb = FakeEmbeddings()
    services = build_services(tmp_settings, embeddings=emb)
    long_text = ("[합성] 문단입니다. " * 30 + "\n\n") * 10
    for page_id in ("1", "2"):
        doc = dataclasses.replace(make_doc(page_id, f"문서{page_id}", text=long_text),
                                  movie_id="157336", related_movie="인터스텔라")  # fmt: skip
        services.raw_store.save(doc)
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    monkeypatch.setattr(reindex_docs, "build_services", lambda s: build_services(s, embeddings=emb))
    assert reindex_docs.main([]) == 0
    first = capsys.readouterr().out
    assert "chunk_size=1000 overlap=200" in first and "문서 2건" in first
    assert reindex_docs.main(["--chunk-size", "500", "--chunk-overlap", "100"]) == 0
    second = capsys.readouterr().out
    assert "chunk_size=500 overlap=100" in second

    def chunks(text):
        return int(text.split("청크 ")[1].split("개")[0])

    assert chunks(second) > chunks(first)


@pytest.mark.parametrize(
    "argv", [["--chunk-size", "500", "--chunk-overlap", "500"], ["--chunk-size", "100"]]
)
def test_tc_f2005_13_reindex_docs_rejects_bad_chunking(tmp_settings, monkeypatch, capsys, argv):
    import dataclasses

    from movielab.container import build_services
    from scripts import reindex_docs
    from tests.fakes import FakeEmbeddings
    from tests.fakes.source import make_doc

    emb = FakeEmbeddings()
    services = build_services(tmp_settings, embeddings=emb)
    services.raw_store.save(dataclasses.replace(make_doc("1", "문서1"), movie_id="157336"))
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    monkeypatch.setattr(reindex_docs, "build_services", lambda s: build_services(s, embeddings=emb))
    with pytest.raises(SystemExit) as exc:
        reindex_docs.main(argv)
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "청크 중복" in captured.err
    assert "chunk overlap" not in captured.err + captured.out  # 라이브러리 영어 원문 없음
    assert emb.calls == 0 and services.store.count("wiki_docs") == 0


def test_tc_f2005_20_reindex_docs_cleans_when_no_raw(tmp_settings, monkeypatch, capsys):
    import dataclasses

    from movielab.container import build_services
    from scripts import reindex_docs
    from tests.fakes import FakeEmbeddings
    from tests.fakes.source import make_doc

    emb = FakeEmbeddings()
    services = build_services(tmp_settings, embeddings=emb)
    doc = dataclasses.replace(make_doc("1", "문서1"), movie_id="157336")
    services.doc_indexer().index_document(doc)  # 원문 저장 없이 색인만 남은 상태
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    monkeypatch.setattr(reindex_docs, "build_services", lambda s: build_services(s, embeddings=emb))
    assert reindex_docs.main([]) == 0
    assert "지웠습니다" in capsys.readouterr().out
    assert services.store.count("wiki_docs") == 0
    assert reindex_docs.main([]) == 1  # 원문도 색인도 없으면 안내
    assert "저장 원문이 없습니다" in capsys.readouterr().out


def test_tc_f2005_25_reindex_movie_id_matches_int_in_raw(tmp_settings, monkeypatch, capsys):
    import dataclasses

    from movielab.container import build_services
    from scripts import reindex_docs
    from tests.fakes import FakeEmbeddings
    from tests.fakes.source import make_doc

    emb = FakeEmbeddings()
    services = build_services(tmp_settings, embeddings=emb)
    doc = dataclasses.replace(make_doc("1", "문서1"), movie_id=157336)  # 원문 JSON에 정수
    services.raw_store.save(doc)
    services.doc_indexer().index_document(doc)
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    monkeypatch.setattr(reindex_docs, "build_services", lambda s: build_services(s, embeddings=emb))
    assert reindex_docs.main(["--movie-id", "157336"]) == 0
    out = capsys.readouterr().out
    assert "문서 1건" in out and "지웠습니다" not in out
    assert services.store.count("wiki_docs") > 0


def test_tc_f2005_30_empty_movie_id_and_override_notice(tmp_settings, monkeypatch, capsys):
    import dataclasses

    from movielab.container import build_services
    from scripts import reindex_docs
    from tests.fakes import FakeEmbeddings
    from tests.fakes.source import make_doc

    emb = FakeEmbeddings()
    services = build_services(tmp_settings, embeddings=emb)
    for movie_id, page_id in (("157336", "1"), ("27205", "2")):
        doc = dataclasses.replace(make_doc(page_id, f"문서{page_id}"), movie_id=movie_id)
        services.raw_store.save(doc)
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    monkeypatch.setattr(reindex_docs, "build_services", lambda s: build_services(s, embeddings=emb))
    assert reindex_docs.main(["--movie-id", ""]) == 0
    out = capsys.readouterr().out
    assert "문서 2건" in out and "되돌" not in out
    assert reindex_docs.main(["--chunk-size", "500", "--chunk-overlap", "100"]) == 0
    assert "되돌" in capsys.readouterr().out


def test_tc_f2005_31_broken_raw_file_skipped_and_kept(tmp_settings, monkeypatch, capsys):
    import dataclasses

    from movielab.container import build_services
    from scripts import reindex_docs
    from tests.fakes import FakeEmbeddings
    from tests.fakes.source import make_doc

    emb = FakeEmbeddings()
    services = build_services(tmp_settings, embeddings=emb)
    indexer = services.doc_indexer()
    for page_id in ("1", "2", "3", "4"):
        doc = dataclasses.replace(make_doc(page_id, f"문서{page_id}"), movie_id="157336")
        services.raw_store.save(doc)
        indexer.index_document(doc)
    services.raw_store.path("157336", "2").write_text("{깨진 json", encoding="utf-8")
    services.raw_store.path("157336", "4").write_text("null", encoding="utf-8")  # 객체가 아닌 JSON
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    monkeypatch.setattr(reindex_docs, "build_services", lambda s: build_services(s, embeddings=emb))
    assert reindex_docs.main([]) == 1  # 실패가 있으면 종료 코드 1
    out = capsys.readouterr().out
    assert "문서 2건" in out and "색인하지 못한 문서 2건" in out
    for page_id in ("2", "4"):  # 읽지 못한 원문의 청크는 유지
        assert services.store.count_where("wiki_docs", {"page_id": page_id}) > 0
