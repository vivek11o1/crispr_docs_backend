import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager


def get_database_url() -> str | None:
    return os.environ.get("SUPABASE_DB_URL")


def get_connection():
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("SUPABASE_DB_URL environment variable is not set")
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)


@contextmanager
def get_cursor():
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                license_key VARCHAR(19) NOT NULL UNIQUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_licenses_key ON licenses(license_key)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses(email)
        """)


def store_license(email: str, license_key: str) -> None:
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO licenses (email, license_key) VALUES (%s, %s)",
            (email, license_key),
        )


def validate_license_key(license_key: str) -> dict:
    license_key = license_key.strip().upper()
    with get_cursor() as cur:
        cur.execute(
            "SELECT license_key, is_active FROM licenses WHERE license_key = %s",
            (license_key,),
        )
        row = cur.fetchone()
        if row is None:
            return {"valid": False, "message": "License key not found"}
        if not row["is_active"]:
            return {"valid": False, "message": "License key is inactive"}
        return {"valid": True, "message": "License is valid"}


def is_database_configured() -> bool:
    return get_database_url() is not None
