## SPEC

- SPEC: `docs/spec/<경로>` (SPEC-<번호>)
- Closes #<이슈번호>

## 인수 조건 (AC)

<!-- SPEC §5의 AC를 모두 옮기고, 충족을 확인한 TC를 적는다 -->

- [ ] AC-<번호>-01 — TC-<번호>-01, TC-<번호>-02
- [ ] AC-<번호>-02 — TC-<번호>-03

## 테스트 결과

- [ ] `ruff check . && ruff format --check . && pytest` 로컬 통과
- [ ] CI 통과
- live 테스트: 실행함(결과: ) / 미실행(사유: )

## 수동 증빙

<!-- SPEC §7 항목. 없으면 "해당 없음" -->

- [ ] `docs/verification/screenshots/...`

## 문서 갱신

- [ ] SPEC 상태 `Done`, 관련 ISSUE 기입
- [ ] `docs/spec/02-traceability.md` 상태 · 이슈 열
- [ ] 가정 추가 · 변경 (`00-product-overview.md` §8): 없음 / A-xx
- [ ] `docs/dev-log.md` (겪은 문제가 있으면)

## 문제와 해결

<!-- 구현 중 막힌 점과 해결 방법. 설계문서 "겪은 문제, 해결 과정"의 원본이 된다 -->

## 리뷰

- [ ] CI 통과 후 새 세션에서 `/code-review <PR번호> --comment` 실행
- [ ] 지적 사항 해결 또는 사유 기록
