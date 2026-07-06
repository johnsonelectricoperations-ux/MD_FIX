# AGENTS.md — Project Rules for AI Assistants

Every AI assistant (Claude, GPT, Gemini, Copilot, etc.) working on this
repository MUST read this file first and follow it. If any instruction here
conflicts with a general habit or preference of the model, this file wins.

## 1. Project Identity (do not change without user approval)

- **Purpose**: Stock investment tooling for the Korean (KRX) and US markets:
  data analysis, backtesting, live/auto trading, dashboards, and alerting.
- **Primary language**: Python 3.11+.
- **Owner**: A single individual investor. Optimize for clarity and safety,
  not for large-team abstractions.
- Do NOT add new languages, frameworks, databases, or paid services without
  explicit user approval. Propose first, implement after approval.

## 2. Language & Encoding Rules

- **Code, comments, docstrings, identifiers, commit messages: English only.**
  Never write Korean in comments, variable names, or function names.
- **User-facing text is Korean**: README, files under `docs/`, log/console
  messages shown to the user, dashboard labels, and alert messages.
- Korean is allowed ONLY inside string literals and Markdown docs.
- All files MUST be UTF-8 (no BOM), LF line endings. Never use cp949/euc-kr.
- Windows console safety: any entry-point script that prints Korean must set
  UTF-8 output explicitly, e.g.:

  ```python
  import sys
  if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
      sys.stdout.reconfigure(encoding="utf-8")
  ```

- Never put Korean in file names, directory names, or CLI argument names.

## 3. Scope Discipline (anti-drift rules)

- Modify only the files directly related to the requested task.
- Make the **minimal diff** that solves the problem. Do not rewrite working
  code wholesale.
- No unrequested refactoring, renaming, file moves, or dependency upgrades.
- Do not change public function signatures or module layout without stating
  the reason and getting approval first.
- If a task seems to require breaking one of these rules, STOP and ask the
  user instead of proceeding.

## 4. Workflow Rules

1. For any non-trivial task, present a short plan BEFORE writing code.
2. After changes, run the tests (`pytest`) and report the actual result.
   Never claim success without running them.
3. Commit messages: `type: short description` in English
   (types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`).
4. When finishing a task:
   - Update the "현재 상태" section of `docs/ROADMAP.md`.
   - If a technical decision was made, append one entry to
     `docs/DECISIONS.md`. Never delete or rewrite past entries.
5. Read `docs/ROADMAP.md` and `docs/DECISIONS.md` at the start of a session
   before making design choices. Do not re-open decisions already recorded
   in `docs/DECISIONS.md`; if you disagree, raise it with the user.

## 5. Trading Safety Rules (CRITICAL — never relax these)

- **Default mode is always simulation/paper trading.** Live order placement
  must require an explicit opt-in flag (e.g. `--live`) AND a confirmation
  step. Never make live trading the default.
- Never place, modify, or cancel a real order as part of a test or demo.
- Every order path must enforce configurable limits: max position size,
  max order amount, and a daily loss cutoff.
- **Secrets**: API keys, account numbers, and tokens live only in `.env`
  (gitignored) and are read via environment variables. Never hard-code them,
  never print them in logs, never commit them. If a secret appears in code
  or git history, alert the user immediately.

## 6. Financial Data Rules

- **Money and prices**: use `Decimal` (or integer minor units), never binary
  `float`, for order amounts, prices, and P&L arithmetic. KRW has no decimal
  places; USD uses 2.
- **Timezones**: all datetimes must be timezone-aware. KRX uses
  `Asia/Seoul`, US markets use `America/New_York`; store/compare in UTC.
  Never use naive `datetime.now()` in market logic.
- **Tickers**: KRX symbols are 6-digit strings (keep leading zeros, e.g.
  `"005930"`); US symbols are uppercase letters. Never store KRX codes as
  integers.
- **Backtesting integrity**: no look-ahead bias — a strategy may only use
  data available at that point in time. State explicitly whether prices are
  adjusted or unadjusted for splits/dividends.
- Market calendars matter: weekends and KR/US holidays differ. Never assume
  both markets are open on the same day.

## 7. Code Conventions

- Follow the `ruff` configuration in `pyproject.toml`; run
  `ruff check .` and `ruff format .` before committing.
- Type hints on all public functions.
- Prefer standard library and already-approved dependencies:
  `pandas`, `numpy`, `requests`, `python-dotenv`, `pytest`.
  Anything else: ask first (see §1).
- Keep modules small and single-purpose. Business logic must be importable
  and testable without network access (inject/fake API clients in tests).
- Tests live in `tests/`, named `test_*.py`. New logic ships with tests;
  bug fixes ship with a regression test.
