---
name: SPEC 구현
about: SPEC 하나를 구현하는 이슈 (SPEC이 먼저 있어야 한다)
title: "[SPEC-<번호>] <이름>"
labels: spec
---

## SPEC

- 문서: `docs/spec/<mvp|advanced|extensions>/SPEC-<번호>-<슬러그>.md`
- 요구사항: <F20xx / NF20xx / X0xx> — <명세서 요구사항명>
- 구분: MVP / 심화 / 확장

## 선행 이슈

- #<번호> (SPEC-<번호>)

## 완료 조건

- [ ] SPEC §5의 AC 전부 충족
- [ ] SPEC §6의 자동 TC 전부 통과 (CI)
- [ ] SPEC §7 수동 증빙 확보 (해당 시)
- [ ] 리뷰 에이전트 리뷰 완료 후 머지
