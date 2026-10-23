"""LangGraph 구조를 mermaid로 출력한다 — 노드 2개(retrieve · generate) 증빙 (F2007 V4.3-2).

python -m scripts.show_graph
"""

from __future__ import annotations

import sys

from movielab.config import load_settings
from movielab.container import build_services
from scripts.index_meta import configure_stdout


def main(argv: list[str] | None = None) -> int:
    configure_stdout()
    services = build_services(load_settings())
    # 구조만 그리므로 검색기 · LLM을 만들지 않는다 (키 없이, Chroma를 열지 않고 실행)
    graph = services.rag_graph_outline()
    print(graph.get_graph().draw_mermaid())
    return 0


if __name__ == "__main__":
    sys.exit(main())
