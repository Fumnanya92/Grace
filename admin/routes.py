# admin/routes.py

from fastapi import APIRouter, Form, File, UploadFile, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyHeader
import os
import json
import shutil

TENANTS_DIR = "tenants"
router = APIRouter()
templates = Jinja2Templates(directory="admin/templates")
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

@router.get("/admin/{tenant_id}", response_class=HTMLResponse)
async def admin_home(request: Request, tenant_id: str):
    return templates.TemplateResponse("upload.html", {"request": request, "tenant_id": tenant_id})

@router.post("/admin/{tenant_id}/upload", response_class=HTMLResponse)
async def upload_file(request: Request, tenant_id: str,
                      file: UploadFile = File(...),
                      file_type: str = Form(...),
                      api_key: str = Depends(api_key_header)):
    if not file or not file_type:
        raise HTTPException(status_code=400, detail="Both file and file_type are required.")

    if api_key != os.getenv("ADMIN_API_KEY"):
        raise HTTPException(status_code=403, detail="Unauthorized")

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

        return RedirectResponse(f"/admin/{tenant_id}?success={file_type}_uploaded", status_code=302)

    except json.JSONDecodeError:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
