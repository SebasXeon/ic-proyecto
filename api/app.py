from fastapi import FastAPI
import os, psycopg2

app = FastAPI()

def db_check() -> bool:
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "db"),
            port=os.getenv("DB_PORT", "5432"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            dbname=os.getenv("POSTGRES_DB", "postgres"),
            connect_timeout=2
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        conn.close()
        return True
    except Exception:
        return False

@app.get("/ping")
def ping():
    return {"status": "ok", "db": db_check()}
