from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from database import (
    init_db,
    store_license,
    validate_license_key,
    is_database_configured,
)
import hashlib
import re
import time
import uuid

LICENSE_KEY_PATTERN = re.compile(r"^YA-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_database_configured():
        try:
            init_db()
        except Exception as exc:
            print(f"Warning: could not initialize database: {exc}")
    yield


app = FastAPI(
    title="Crispr License API",
    description="Backend API for Crispr license generation and validation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LicenseGenerateRequest(BaseModel):
    email: EmailStr


class LicenseGenerateResponse(BaseModel):
    license_key: str
    message: str


class LicenseValidateRequest(BaseModel):
    license_key: str


class LicenseValidateResponse(BaseModel):
    valid: bool
    message: str


class HealthResponse(BaseModel):
    status: str
    database: str


def generate_license_key(email: str) -> str:
    seed = f"{email}-{time.time()}-{uuid.uuid4()}"
    hash_bytes = hashlib.sha256(seed.encode()).hexdigest().upper()
    segment1 = hash_bytes[0:4]
    segment2 = hash_bytes[4:8]
    segment3 = hash_bytes[8:12]
    return f"YA-{segment1}-{segment2}-{segment3}"


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    db_status = "connected" if is_database_configured() else "not configured"
    return HealthResponse(status="ok", database=db_status)


@app.post("/api/license/generate", response_model=LicenseGenerateResponse)
async def generate_license(request: LicenseGenerateRequest):
    license_key = generate_license_key(request.email)

    if is_database_configured():
        try:
            store_license(request.email, license_key)
        except Exception:
            raise HTTPException(
                status_code=503,
                detail="License could not be saved: database unavailable. Please try again later.",
            )

    message = "License key generated successfully. On your first run, crispr will prompt you for this license key."
    return LicenseGenerateResponse(license_key=license_key, message=message)


@app.post("/api/license/validate", response_model=LicenseValidateResponse)
async def validate_license(request: LicenseValidateRequest):
    license_key = request.license_key.strip().upper()
    if not LICENSE_KEY_PATTERN.match(license_key):
        raise HTTPException(status_code=400, detail="Invalid license key format")

    if not is_database_configured():
        raise HTTPException(
            status_code=503,
            detail="License validation unavailable: database not configured",
        )

    try:
        result = validate_license_key(license_key)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="License validation unavailable: database error",
        )
    if not result["valid"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return LicenseValidateResponse(valid=True, message=result["message"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
