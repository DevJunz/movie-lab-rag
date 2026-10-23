"""테스트 중에 합성 PDF를 바이트로 만든다 (SPEC-F2016 §2.3.1). 바이너리 픽스처를 저장소에 넣지 않는다.

표준 Type1 글꼴(Helvetica)만 쓰므로 ASCII 텍스트만 넣는다. 쪽마다 줄 목록을 받는다(빈 목록 = 빈 쪽).
"""

from __future__ import annotations

from pathlib import Path


def _escape(line: str) -> str:
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content(lines: list[str]) -> bytes:
    if not lines:
        return b""
    ops = ["BT", "/F1 10 Tf", "12 TL", "40 800 Td"]
    for line in lines:
        ops.append(f"({_escape(line)}) Tj T*")
    ops.append("ET")
    return "\n".join(ops).encode("latin-1")


def make_pdf(pages: list[list[str]]) -> bytes:
    """`pages[i]`는 i+1쪽의 줄 목록. 최소 구조의 PDF 1.4 바이트를 돌려준다."""
    objects: list[bytes] = []
    n_pages = len(pages)
    font_id = 3
    page_ids = [4 + 2 * i for i in range(n_pages)]
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, lines in enumerate(pages):
        content_id = page_ids[i] + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode()
        )
        stream = _content(lines)
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def write_pdf(path: Path, pages: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(make_pdf(pages))
    return path
