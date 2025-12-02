from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from psycopg2.extras import RealDictCursor
import os, psycopg2

app = FastAPI()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        port=os.getenv("DB_PORT", "5432"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "postgres"),
        connect_timeout=2
    )

def db_check() -> bool:
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        conn.close()
        return True
    except Exception:
        return False

def init_db():
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    completed BOOLEAN NOT NULL DEFAULT FALSE
                );
                """
            )
    conn.close()

class TodoBase(BaseModel):
    title: str
    completed: bool = False

class TodoCreate(TodoBase):
    pass

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None

class Todo(TodoBase):
    id: int

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/ping")
def ping():
    return {"status": "ok", "db": db_check()}

@app.get("/todos", response_model=List[Todo])
def list_todos():
    conn = get_db_connection()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, title, completed FROM todos ORDER BY id;")
            todos = cur.fetchall()
    conn.close()
    return todos

@app.post("/todos", response_model=Todo, status_code=status.HTTP_201_CREATED)
def create_todo(todo: TodoCreate):
    conn = get_db_connection()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO todos (title, completed) VALUES (%s, %s) RETURNING id, title, completed;",
                (todo.title, todo.completed),
            )
            new_todo = cur.fetchone()
    conn.close()
    return new_todo

@app.put("/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, todo: TodoUpdate):
    if todo.title is None and todo.completed is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide a field to update.")

    conn = get_db_connection()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, title, completed FROM todos WHERE id = %s;", (todo_id,))
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found.")

            new_title = todo.title if todo.title is not None else existing["title"]
            new_completed = todo.completed if todo.completed is not None else existing["completed"]

            cur.execute(
                "UPDATE todos SET title = %s, completed = %s WHERE id = %s RETURNING id, title, completed;",
                (new_title, new_completed, todo_id),
            )
            updated = cur.fetchone()
    conn.close()
    return updated

@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int):
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM todos WHERE id = %s;", (todo_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found.")
    conn.close()
