# admin/routes.py

from fastapi import APIRouter, Form, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import json
import shutil

TENANTS_DIR = "tenants"
router = APIRouter()
templates = Jinja2Templates(directory="admin/templates")

@router.get("/admin/{tenant_id}", response_class=HTMLResponse)
async def admin_home(request: Request, tenant_id: str):
    return templates.TemplateResponse("upload.html", {"request": request, "tenant_id": tenant_id})

@router.post("/admin/{tenant_id}/upload", response_class=HTMLResponse)
async def upload_file(request: Request, tenant_id: str,
                      file: UploadFile = File(...),
                      file_type: str = Form(...)):
    tenant_path = os.path.join(TENANTS_DIR, tenant_id)
    os.makedirs(tenant_path, exist_ok=True)

    # Map file_type to filename
    filename_map = {
        "catalog": "catalog.json",
        "config": "config.json",
        "tone": "tone.json",
        "speech_library": "speech_library.json"
    }

    if file_type not in filename_map:
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_path = os.path.join(tenant_path, filename_map[file_type])

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validate uploaded JSON
        with open(file_path, "r") as f:
            json.load(f)

        return RedirectResponse(f"/admin/{tenant_id}?success={file_type}", status_code=302)

    except json.JSONDecodeError:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
