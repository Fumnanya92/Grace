from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
import os, json, shutil
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
TENANTS_DIR = "tenants"
ASSET_TYPES = ["catalog", "tone", "config", "fallback_responses"]

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

def get_tenant_map() -> dict:
    mapping_path = os.path.join(TENANTS_DIR, "tenant_map.json")
    if os.path.exists(mapping_path):
        with open(mapping_path) as f:
            return json.load(f)
    return {}

@router.post("/upload_asset")
async def upload_asset(
    tenant_id: str = Form(...),
    asset_type: str = Form(...),
    file: UploadFile = File(...),
    api_key: str = Depends(api_key_header)
):
    if api_key != os.getenv("ADMIN_API_KEY"):
        raise HTTPException(status_code=403, detail="Unauthorized")

    if asset_type not in ASSET_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported asset_type. Use one of: {ASSET_TYPES}")

    tenant_path = os.path.join(TENANTS_DIR, tenant_id)
    os.makedirs(tenant_path, exist_ok=True)
    dest_path = os.path.join(tenant_path, f"{asset_type}.json")

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        with open(dest_path, "r") as f:
            json.load(f)  # Validate it's proper JSON

        return JSONResponse(content={"message": f"{asset_type}.json uploaded successfully for {tenant_id}"})

    except json.JSONDecodeError:
        os.remove(dest_path)
        raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
