# Orbit AI — Intelligent Operations Agent

> Repository: **Orbit-I**

Orbit AI turns plain-language operations requests into reviewable task, reminder, and workflow plans. It is a FastAPI + SQLite backend paired with a responsive React/Vite dashboard, created for the TriCity AI Hackathon.

## Quick start on Windows

1. Install **Python 3.11** (via the Windows Python launcher) and **Node.js 20+**.
2. Double-click `setup.bat`.
3. Optionally add `OPENAI_API_KEY` to `.env` or `backend/.env`.
4. Double-click `run.bat`, then open `http://localhost:5173`.

Without an API key, Orbit displays a clearly labelled safe fallback plan that can be edited/reviewed before applying. With a key, the backend uses the official OpenAI Python SDK; no secret is sent to the browser.

## Demo route

The app starts with isolated demo workspace data: **TriCity AI Hackathon Submission**, seven realistic tasks, a reminder, and a workflow. Use **Reset demo** in the sidebar to return to a consistent state for judges.

Try: `Create a high-priority task to finish the presentation by Friday.` Then review the generated preview and choose **Approve & apply**.

## Architecture and security

- `backend/main.py` provides validated REST endpoints, OpenAPI at `http://127.0.0.1:8000/docs`, SQLite persistence, ownership checks, activity logs, AI fallback/error handling, and CORS.
- The demo identity is intentionally local. The `current_user` dependency is the one integration point to replace with Firebase Admin SDK token verification for production deployment.
- All records carry a `user_id`; resource lookup checks ownership before update/delete/run operations.
- The database is stored in `backend/orbit.db` by default and survives refreshes/restarts.

## Test and package

Run `test.bat` for backend API tests plus the frontend production build. To make a submission archive, zip the `orbit-ai` directory while excluding `.venv`, `node_modules`, `.env`, `*.db`, and `dist` (already covered by `.gitignore`).

## GitHub upload

Create an empty GitHub repository, then in this folder run `git init`, `git add .`, `git commit -m "Build Orbit AI"`, set the remote, and push. Never commit `.env` files.

See `docs/presentation.md` for the pitch and live-demo script.
