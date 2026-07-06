# ROADMAP — 진행 상태와 계획

> AI 규칙: 작업을 끝낼 때마다 "현재 상태"를 갱신할 것. 완료 항목은 삭제하지
> 말고 완료 표시(✅)로 남길 것.

## 프로젝트 목표

한국(KRX)·미국 주식 대상 개인 투자 도구:

1. 데이터 수집·분석·백테스팅
2. 자동매매 (기본은 모의투자, 실거래는 명시적 승인 필요)
3. 대시보드·시각화
4. 조건 충족 시 알림(모니터링)

## 현재 상태 (2026-07-06)

- ✅ AI 협업 규칙 체계 구축 (AGENTS.md, CLAUDE.md, DECISIONS.md, ROADMAP.md,
  ruff/editorconfig 설정)
- ✅ 전략 결정: ETF 모멘텀 로테이션 + 변동성 목표 + 급락 대피 (D-006)
- ✅ 프로젝트 뼈대: `stock/` 패키지, `scripts/`, `tests/`, requirements.txt
- ✅ 데이터 모듈: yfinance 수집 + CSV 캐시 (`stock/data.py`, D-007)
- ✅ 전략·백테스트 엔진: `stock/strategy.py`, `stock/backtest.py`,
  `stock/metrics.py` — 합성 데이터 테스트 13개 통과 (look-ahead 방지,
  급락 대피, 변동성 축소, 비용 계산 검증)
- ⬜ **실제 데이터로 백테스트 실행 — 사용자 PC에서 필요**
  (원격 AI 환경은 시세 사이트 접속 차단):
  1. `pip install -r requirements.txt`
  2. `python scripts/fetch_data.py` (데이터 다운로드)
  3. `python scripts/run_backtest.py` (결과 출력)

## 다음 할 일 (우선순위 순)

1. ⬜ 실데이터 백테스트 결과 검토 — 특히 2026-06 급락 구간 손실 확인
2. ⬜ 설정값 비교 실험 (모멘텀 기간, 급락 대피 기준, 후보군 확장)
3. ⬜ 급락 구간(2008, 2020, 2022)을 포함한 장기 검증 — ETF 상장 전
   구간은 지수 데이터로 보완할지 결정 필요
4. ⬜ 모의투자 연동 (증권사 API 선택 후)
5. ⬜ 대시보드 / 알림 (이후 결정)

## 보류 / 미결정 사항

- 증권사 API 선택 (한국투자증권 / 키움 등) — 사용자 결정 필요
- 대시보드 기술 (Streamlit 등) — 필요해질 때 결정
