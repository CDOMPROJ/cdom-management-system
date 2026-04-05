# CDOM Pastoral Management System - Backend

A FastAPI-based pastoral management system for the Catholic Diocese of Mansa.

## Quick Start (No manual fixes required)

1. Clone the repo
2. Copy `.env.example` → `.env` and fill the values
3. `pip install -r requirements.txt`
4. Start PostgreSQL: `docker-compose up -d db`
5. Run the backend: `docker-compose up backend`  
   → **Migrations run automatically** on every start (development/staging)

## Local Development (without Docker)
```bash
pip install -r requirements.txt
docker-compose up -d db
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload