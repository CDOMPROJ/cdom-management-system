# CDOM Pastoral Management System - Backend

A FastAPI-based pastoral management system for the Catholic Diocese of Mansa.

## Setup Instructions
1. Clone the repo
2. Copy `.env.example` → `.env` and fill values
3. `pip install -r app/requirements.txt`
4. Start PostgreSQL (see docker-compose.yml)
5. Run migrations: `alembic -c app/alembic.ini upgrade head`
6. Start server: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

## Docker
See `docker-compose.yml` and `Dockerfile`.

## API
Swagger: http://localhost:8000/docs  
All endpoints under `/api/v1/`

## Production Notes
- CORS restricted
- HTTPS enforced
- Security headers enabled
- Prometheus metrics at `/metrics`

For frontend integration see the paired Flutter repo.