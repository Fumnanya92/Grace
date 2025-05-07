# catalog_upload.py
from fastapi import APIRouter, UploadFile, File
import os, json, csv

router = APIRouter()
CATALOG_PATH = "catalog_store.json"

@router.post("/upload_catalog")
async def upload_catalog(file: UploadFile = File(...)):
    if file.filename.endswith(".csv"):
        content = await file.read()
        lines = content.decode().splitlines()
        reader = csv.DictReader(lines)
        data = [dict(row) for row in reader]
    elif file.filename.endswith(".json"):
        data = json.loads(await file.read())
    else:
        return {"error": "Unsupported file format. Upload CSV or JSON."}

    with open(CATALOG_PATH, "w") as f:
        json.dump(data, f, indent=4)
    return {"status": "Catalog uploaded successfully.", "items": len(data)}
