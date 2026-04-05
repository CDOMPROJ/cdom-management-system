# CDOM Pastoral Management System - Backend

A FastAPI-based pastoral management system for the Catholic Diocese of Mansa.

## Setup Instructions (PostgreSQL + Alembic + Uvicorn)

1. Clone the repo
2. Copy `.env.example` → `.env` and fill values
3. Install dependencies: `pip install -r app/requirements.txt`
4. Start PostgreSQL (see docker-compose below)
5. Run migrations: `alembic -c app/alembic.ini upgrade head`
6. Start server: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

## Docker / docker-compose (recommended)

See `docker-compose.yml` and `Dockerfile` at root.

## API Usage & Swagger

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- All endpoints under `/api/v1/`
- JWT auth: use `/api/v1/auth/login` → add `Authorization: Bearer <token>` to all other calls

## Production Notes

- CORS is now restricted (see main.py)
- HTTPS enforced via middleware
- Security headers enabled
- Use Uvicorn with `--workers` and behind a reverse proxy (Nginx/Traefik) for production

For frontend integration see the paired Flutter repo.