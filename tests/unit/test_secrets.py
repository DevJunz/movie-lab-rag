"""SPEC-NF2003 — 저장소에 비밀 값이 없고, .env가 추적되지 않는다."""

from __future__ import annotations

from tests.secret_scan import ROOT, scan_repo, scan_text, tracked_files

REQUIRED_IGNORES = [
    ".env",
    "/data/",
    "영화도메인_데이터_배포용/",
    "prd.pdf",
    "rag_project_briefing.html",
]


def test_tc_nf2003_04_no_secrets_in_repo():
    findings = scan_repo()
    assert findings == [], "비밀 값으로 보이는 문자열:\n" + "\n".join(map(str, findings))


def test_tc_nf2003_04_env_not_tracked():
    files = tracked_files()
    assert ".env" not in files
    assert ".env.example" in files


def test_tc_nf2003_04_gitignore_has_required_entries():
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in REQUIRED_IGNORES:
        assert entry in lines, f".gitignore에 '{entry}' 없음"


def test_tc_nf2003_04_env_example_has_no_values():
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, _, value = line.partition("=")
        assert value.strip() in ("", "false"), f".env.example의 {name}에 값이 있다"
    names = {
        line.split("=")[0]
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    }
    assert {"GMS_API_KEY", "GMS_BASE_URL", "WIKI_CONTACT"} <= names


def test_tc_nf2003_05_scanner_detects_keys():
    leaked = "OPENAI = 'sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2'"
    assert scan_text(leaked)
    assert scan_text('api_key = "' + "x9" * 10 + '"')
    assert scan_text('GMS_TOKEN: "' + "abcd" * 5 + '"')
    # 허용: 테스트용 가짜 키, 짧은 값, 변수 이름만 있는 경우
    assert not scan_text("key = 'sk-test-abcdefghijklmnopqrstuvwxyz'")
    assert not scan_text('api_key = "short"')
    assert not scan_text("api_key=settings.secrets.gms_api_key")


def test_tc_nf2003_10_unquoted_env_style_lines_detected():
    assert scan_text("GMS_API_KEY=" + "Ab3" * 8)
    assert scan_text("export OPENAI_SECRET=" + "z9" * 12)
    assert not scan_text("GMS_API_KEY=")  # .env.example 형식
    assert not scan_text("api_key=settings.secrets.gms_api_key")


def test_tc_nf2003_10_allowlist_is_prefix_only():
    assert not scan_text('api_key = "sk-test-' + "a" * 20 + '"')
    assert scan_text('api_key = "live-sk-test-' + "a" * 20 + '"')
    assert scan_text("token: 'xsk-test-" + "b" * 20 + "'")


def test_tc_nf2003_10_finding_does_not_print_value():
    secret = "sk-" + "Q" * 30
    finding = scan_text("key = " + secret, "a.py")[0]
    assert "Q" * 5 not in str(finding) and "sk-" not in str(finding)
    assert "a.py:1" in str(finding)


def test_tc_nf2003_10_fallback_without_git_skips_env_and_venv(tmp_path):
    (tmp_path / ".env").write_text("GMS_API_KEY=" + "x" * 30, encoding="utf-8")
    (tmp_path / ".env.local").write_text("x", encoding="utf-8")
    (tmp_path / ".env.example").write_text("GMS_API_KEY=", encoding="utf-8")
    for folder in ("venv", ".venv", "__pycache__", ".pytest_cache", "data"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "x.py").write_text("x", encoding="utf-8")
    (tmp_path / "prd.pdf").write_text("x", encoding="utf-8")
    (tmp_path / "app.py").write_text("x", encoding="utf-8")
    assert sorted(tracked_files(tmp_path)) == [".env.example", "app.py"]
