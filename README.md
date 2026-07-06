# 주식투자 코딩 프로젝트

한국(KRX)·미국 주식을 대상으로 하는 개인 투자 도구 모음입니다.
데이터 분석·백테스팅, 자동매매, 대시보드, 알림 기능을 목표로 합니다.

## AI 협업 규칙 체계

이 저장소는 어떤 AI 모델(Claude, GPT, Gemini 등)을 사용하더라도 일관되게
개발이 이어지도록 다음 파일들로 규칙을 관리합니다.

| 파일 | 역할 |
|------|------|
| `AGENTS.md` | **모든 규칙의 원본.** 모든 AI가 작업 시작 전에 반드시 읽어야 하는 파일 (영어) |
| `CLAUDE.md` | Claude Code용 진입점 — AGENTS.md를 참조하라는 안내만 포함 |
| `docs/ROADMAP.md` | 현재 진행 상태와 다음 할 일 — 세션이 바뀌어도 맥락이 이어지는 장치 |
| `docs/DECISIONS.md` | 기술 결정 기록 — 이미 내린 결정을 AI가 다시 뒤집지 않게 하는 장치 |
| `pyproject.toml` | ruff 린트/포맷 설정 — 규칙을 기계적으로 강제 |
| `.editorconfig` | UTF-8, LF 줄바꿈 강제 — 한글 인코딩 오류 방지 |

## 핵심 규칙 요약 (자세한 내용은 AGENTS.md)

- 코드·주석·변수명·커밋 메시지는 **영어**, 문서와 화면 출력은 **한국어**
- 모든 파일은 UTF-8 — cp949로 인한 한글 깨짐/오류 방지
- 요청받은 작업만, 최소한의 수정으로 — 멋대로 리팩토링 금지
- 매매 코드는 **기본이 모의투자**, 실주문은 명시적 플래그 + 확인 필수
- API 키·계좌번호는 `.env`에만 보관, 절대 커밋 금지
- 돈 계산은 `Decimal`, 시간은 타임존 포함(KRX=Asia/Seoul, 미국=America/New_York)
- 작업이 끝나면 `docs/ROADMAP.md` 갱신, 새 결정은 `docs/DECISIONS.md`에 기록

## 새 AI 세션을 시작할 때

AI에게 다음과 같이 요청하면 됩니다:

> AGENTS.md와 docs/ROADMAP.md, docs/DECISIONS.md를 먼저 읽고 시작해줘.
> 오늘 할 일은 ○○○이야.

## 개발 환경

- Python 3.11 이상
- 의존성 설치: `pip install -r requirements.txt` (프로젝트 시작 후 생성 예정)
- 검사: `ruff check .` / 포맷: `ruff format .` / 테스트: `pytest`
