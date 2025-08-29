# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: FastAPI app. Key files: `api.py` (routes), `services/` (business logic), `db.py` (SQLite access), `logs.py` (logging), `data/` (runtime files).
- `frontend/`: React + Vite + TypeScript. Key dirs: `src/pages`, `src/components`, `src/services`.
- `scripts/`: Dev helpers (`dev.sh`, `dev-fast.sh`).
- `seeds/`: CSV seed data. `schema.sql`: DB schema.
- Config: `config.yaml` (auto-created). Frontend env: `frontend/.env`.

## Build, Test, and Development Commands
- Start both (installs if needed): `bash scripts/dev.sh`
- Fast start (skip installs): `bash scripts/dev-fast.sh`
- Manual backend: `uvicorn backend.api:app --reload --port 8000`
- Manual frontend: `cd frontend && npm run dev`
- Frontend build/preview: `npm run build` / `npm run preview`
- Lint (frontend): `npm run lint`

## Coding Style & Naming Conventions
- Python: 4‑space indent, snake_case for functions/vars, PascalCase for classes. Keep route handlers thin; put logic in `services/`. Use `logs.py` instead of ad‑hoc prints.
- TypeScript/React: PascalCase components (`PositionTable.tsx`), camelCase hooks/utils, colocate view code under `src/pages`. Prefer function components with hooks.
- ESLint is configured for the frontend; fix issues before pushing.

## Testing Guidelines
- No formal test suite yet. Recommended:
  - Backend: `pytest` under `backend/tests/` (e.g., `test_positions.py`), focusing on `services/` and API contracts.
  - Frontend: Vitest + React Testing Library with `*.test.tsx` under `frontend/src/`.
- Keep tests fast and deterministic; aim for meaningful coverage of critical flows.

## Commit & Pull Request Guidelines
- Commits: short, imperative subject (English or Chinese), scope when useful (e.g., `backend: fix snapshot calc`). Reference issues if applicable.
- PRs: clear description, linked issues, screenshots/GIFs for UI changes, steps to verify, and any schema/config changes noted. Keep PRs focused and pass lints/build.

## Security & Configuration Tips
- Do not commit secrets. Keep tokens (e.g., `tushare_token`) only in local `config.yaml`. Frontend API base lives in `frontend/.env` via `VITE_API_BASE`.
- Configure DB path via `config.yaml` (`db_path: ./portfolio.db`). Avoid committing local DB artifacts.

## Architecture Overview
- Backend: FastAPI REST over SQLite (`db.py`), centralized logging, service‑oriented modules.
- Frontend: Vite + React + TS, talks to backend via `VITE_API_BASE`.
