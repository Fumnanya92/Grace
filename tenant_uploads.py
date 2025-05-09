from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
import os, json, shutil
from dotenv import load_dotenv
import logging
load_dotenv()

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

router = APIRouter()
TENANTS_DIR = "tenants"

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

def get_tenant_map() -> dict:
    mapping_path = os.path.join(TENANTS_DIR, "tenant_map.json")
    if os.path.exists(mapping_path):
        with open(mapping_path) as f:
            return json.load(f)
    return {}

def validate_json_schema(data: dict, file_type: str):
    required_fields = {
        "catalog": ["id", "name", "description", "price"],
        "tone": ["tone_id", "tone_name"],
        "fallback_responses": ["response_id", "response_text"],
        "config": ["setting", "value"]
    }
    for field in required_fields.get(file_type, []):
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

@router.post("/admin/{tenant_id}/upload", response_class=HTMLResponse)
async def upload_file(request: Request, tenant_id: str,
                      file: UploadFile = File(...),
                      file_type: str = Form(...),
                      api_key: str = Depends(api_key_header)):
    tenant_map = get_tenant_map()
    tenant_info = tenant_map.get(tenant_id)

    # Validate tenant and API key
    if not tenant_info:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    if tenant_info.get("api_key") != api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Ensure tenant directory exists
    tenant_path = os.path.join(TENANTS_DIR, tenant_id)
    os.makedirs(tenant_path, exist_ok=True)

    # Map file types to filenames
    filename_map = {
        "catalog": "catalog.json",
        "tone": "tone.json",
        "fallback_responses": "fallback_responses.json",
        "config": "config.json"
    }

    if file_type not in filename_map:
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_path = os.path.join(tenant_path, filename_map[file_type])

    try:
        # Save the uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validate JSON format and schema
        with open(file_path, "r") as f:
            data = json.load(f)
            validate_json_schema(data, file_type)

        logger.info(f"File '{file_type}' uploaded successfully for tenant '{tenant_id}'")
        return RedirectResponse(f"/admin/{tenant_id}?success={file_type}_uploaded", status_code=302)

    except json.JSONDecodeError as e:
        os.remove(file_path)
        logger.error(f"Invalid JSON file uploaded for tenant '{tenant_id}': {e}")
        raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON")

    except Exception as e:
        logger.error(f"Error uploading file for tenant '{tenant_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))
