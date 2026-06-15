from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic import BaseModel
from uuid import uuid4
import os
import requests

DATABASE_URL = os.getenv("DATABASE_URL")
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================
# MODELS
# =====================

class Request(Base):
    __tablename__ = "requests"
    id = Column(String, primary_key=True)
    name = Column(String)
    phone = Column(String)
    comment = Column(Text)
    status = Column(String, default="new")


class Jewelry(Base):
    __tablename__ = "jewelry"
    id = Column(String, primary_key=True)
    image_url = Column(String)


Base.metadata.create_all(bind=engine)


# =====================
# DTO
# =====================

class RequestDTO(BaseModel):
    name: str
    phone: str
    comment: str | None = None


class RequestStatusDTO(BaseModel):
    status: str


# =====================
# REQUESTS
# =====================

@app.post("/requests")
def create_request(data: RequestDTO):
    db = SessionLocal()
    try:
        req = Request(
            id=str(uuid4()),
            name=data.name,
            phone=data.phone,
            comment=data.comment,
            status="new"
        )
        db.add(req)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.get("/requests")
def get_requests():
    db = SessionLocal()
    try:
        return db.query(Request).all()
    finally:
        db.close()


@app.patch("/requests/{request_id}/status")
def update_request_status(request_id: str, data: RequestStatusDTO):
    allowed = ["new", "in_progress", "done"]
    if data.status not in allowed:
        raise HTTPException(400, f"Status must be one of: {allowed}")
    db = SessionLocal()
    try:
        req = db.query(Request).filter(Request.id == request_id).first()
        if not req:
            raise HTTPException(404, "Not found")
        req.status = data.status
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.delete("/requests/{request_id}")
def delete_request(request_id: str):
    db = SessionLocal()
    try:
        req = db.query(Request).filter(Request.id == request_id).first()
        if not req:
            raise HTTPException(404, "Not found")
        db.delete(req)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


# =====================
# YANDEX DISK UPLOAD
# =====================

def upload_to_yandex(file: UploadFile):
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    filename = f"{uuid4()}_{file.filename}"

    r = requests.get(
        "https://cloud-api.yandex.net/v1/disk/resources/upload",
        headers=headers,
        params={"path": f"/jewelry/{filename}", "overwrite": "true"}
    )

    upload_url = r.json()["href"]
    requests.put(upload_url, files={"file": file.file})

    requests.put(
        "https://cloud-api.yandex.net/v1/disk/resources/publish",
        headers=headers,
        params={"path": f"/jewelry/{filename}"}
    )

    info = requests.get(
        "https://cloud-api.yandex.net/v1/disk/resources",
        headers=headers,
        params={"path": f"/jewelry/{filename}"}
    )

    return info.json()["public_url"]


# =====================
# JEWELRY
# =====================

@app.post("/cards/upload")
def upload_card(file: UploadFile = File(...)):
    db = SessionLocal()
    try:
        url = upload_to_yandex(file)
        card = Jewelry(
            id=str(uuid4()),
            image_url=url
        )
        db.add(card)
        db.commit()
        return {"image_url": url}
    finally:
        db.close()


@app.get("/cards")
def get_cards():
    db = SessionLocal()
    try:
        return db.query(Jewelry).all()
    finally:
        db.close()


# =====================
# ROOT
# =====================

@app.get("/")
def root():
    return {"status": "ok"}