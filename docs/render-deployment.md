# Render deployment

Orbit is one Docker **Web Service**. The Docker build compiles the Vite frontend and FastAPI serves the resulting files, so the browser and API share one public origin.

## Required Render settings

- **Repository:** `krishnapodishetti18/Orbit-I`
- **Branch:** `main`
- **Runtime:** Docker
- **Dockerfile path:** `Dockerfile`
- **Health check path:** `/health`
- **Start command:** supplied by the Dockerfile: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Persistent SQLite MVP

SQLite must use a Render Persistent Disk; the default container filesystem is ephemeral. In the Render service dashboard:

1. Open **Disks** and select **Add Disk**.
2. Set the mount path to `/var/data` and choose a disk size.
3. Save the disk configuration, then open **Environment**.
4. Add `DATABASE_URL` with the value `sqlite:////var/data/orbit.db`.
5. Redeploy the latest `main` commit.

Render Persistent Disks require a paid Web Service plan. Do not create the disk until you have selected and accepted the applicable Render plan.

## Managed PostgreSQL alternative

Create a Render Postgres instance and set `DATABASE_URL` to its internal SQLAlchemy-compatible connection URL, using `postgresql+psycopg://` if needed. The included `psycopg` driver supports this configuration. This is the recommended production option and requires no application code change.

## Secrets

Set `OPENAI_API_KEY` only in Render **Environment** when live AI is required. It is optional: Orbit produces an editable local fallback plan when it is absent.
