"""
Settings API endpoints for Archon

Handles:
- OpenAI API key management
- Other credentials and configuration
- Settings storage and retrieval
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import json
from datetime import datetime

from ..utils import get_supabase_client
from ..credential_service import credential_service, CredentialItem, initialize_credentials

router = APIRouter(prefix="/api", tags=["settings"])

class SetOpenAIKeyRequest(BaseModel):
    api_key: str

class CredentialRequest(BaseModel):
    key: str
    value: str
    is_encrypted: bool = False
    category: Optional[str] = None
    description: Optional[str] = None

class CredentialUpdateRequest(BaseModel):
    value: str
    is_encrypted: Optional[bool] = None
    category: Optional[str] = None
    description: Optional[str] = None

class CredentialResponse(BaseModel):
    success: bool
    message: str

@router.get("/openai-key/status")
async def get_openai_key_status():
    """Check if OpenAI API key is configured."""
    try:
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("credentials").select("key_value").eq("key_name", "openai_api_key").execute()
        
        has_key = bool(response.data)
        
        return {
            "configured": has_key,
            "message": "OpenAI API key is configured" if has_key else "OpenAI API key not configured"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/openai-key", response_model=CredentialResponse)
async def set_openai_key(request: SetOpenAIKeyRequest):
    """Set the OpenAI API key."""
    try:
        supabase_client = get_supabase_client()
        
        # Check if key already exists
        existing = supabase_client.table("credentials").select("id").eq("key_name", "openai_api_key").execute()
        
        if existing.data:
            # Update existing key
            response = supabase_client.table("credentials").update({
                "key_value": request.api_key
            }).eq("key_name", "openai_api_key").execute()
        else:
            # Insert new key
            response = supabase_client.table("credentials").insert({
                "key_name": "openai_api_key",
                "key_value": request.api_key
            }).execute()
        
        if response.data:
            return CredentialResponse(
                success=True,
                message="OpenAI API key saved successfully"
            )
        else:
            return CredentialResponse(
                success=False,
                message="Failed to save OpenAI API key"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.delete("/openai-key", response_model=CredentialResponse)
async def delete_openai_key():
    """Delete the stored OpenAI API key."""
    try:
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("credentials").delete().eq("key_name", "openai_api_key").execute()
        
        return CredentialResponse(
            success=True,
            message="OpenAI API key deleted successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

# Credential Management Endpoints
@router.get("/credentials")
async def list_credentials(category: Optional[str] = None):
    """List all credentials and their categories."""
    try:
        credentials = await credential_service.list_all_credentials()
        
        # Filter by category if specified
        if category:
            credentials = [cred for cred in credentials if cred.category == category]
        
        return [
            {
                'key': cred.key,
                'value': cred.value,
                'encrypted_value': cred.encrypted_value,
                'is_encrypted': cred.is_encrypted,
                'category': cred.category,
                'description': cred.description
            }
            for cred in credentials
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/credentials/categories/{category}")
async def get_credentials_by_category(category: str):
    """Get all credentials for a specific category."""
    try:
        credentials = await credential_service.get_credentials_by_category(category)
        return {'credentials': credentials}
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/credentials")
async def create_credential(request: CredentialRequest):
    """Create or update a credential."""
    try:
        success = await credential_service.set_credential(
            key=request.key,
            value=request.value,
            is_encrypted=request.is_encrypted,
            category=request.category,
            description=request.description
        )
        
        if success:
            return {
                'success': True,
                'message': f'Credential {request.key} {"encrypted and " if request.is_encrypted else ""}saved successfully'
            }
        else:
            raise HTTPException(status_code=500, detail={'error': 'Failed to save credential'})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/credentials/{key}")
async def get_credential(key: str, decrypt: bool = True):
    """Get a specific credential by key."""
    try:
        value = await credential_service.get_credential(key, decrypt=decrypt)
        
        if value is None:
            raise HTTPException(status_code=404, detail={'error': f'Credential {key} not found'})
        
        # For encrypted credentials, return metadata instead of the actual value for security
        if isinstance(value, dict) and value.get('is_encrypted') and not decrypt:
            return {
                'key': key,
                'is_encrypted': True,
                'category': value.get('category'),
                'description': value.get('description'),
                'has_value': bool(value.get('encrypted_value'))
            }
        
        return {
            'key': key,
            'value': value,
            'is_encrypted': False
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.put("/credentials/{key}")
async def update_credential(key: str, request: Dict[str, Any]):
    """Update an existing credential."""
    try:
        # Handle both CredentialUpdateRequest and full Credential object formats
        if isinstance(request, dict):
            # If the request contains a 'value' field directly, use it
            value = request.get('value', '')
            is_encrypted = request.get('is_encrypted')
            category = request.get('category')
            description = request.get('description')
        else:
            value = request.value
            is_encrypted = request.is_encrypted
            category = request.category
            description = request.description
            
        # Get existing credential to preserve metadata if not provided
        existing_creds = await credential_service.list_all_credentials()
        existing = next((c for c in existing_creds if c.key == key), None)
        
        if existing is None:
            # If credential doesn't exist, create it
            is_encrypted = is_encrypted if is_encrypted is not None else False
        else:
            # Preserve existing values if not provided
            if is_encrypted is None:
                is_encrypted = existing.is_encrypted
            if category is None:
                category = existing.category
            if description is None:
                description = existing.description
        
        success = await credential_service.set_credential(
            key=key,
            value=value,
            is_encrypted=is_encrypted,
            category=category,
            description=description
        )
        
        if success:
            return {
                'success': True,
                'message': f'Credential {key} updated successfully'
            }
        else:
            raise HTTPException(status_code=500, detail={'error': 'Failed to update credential'})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.delete("/credentials/{key}")
async def delete_credential(key: str):
    """Delete a credential."""
    try:
        success = await credential_service.delete_credential(key)
        
        if success:
            return {
                'success': True,
                'message': f'Credential {key} deleted successfully'
            }
        else:
            raise HTTPException(status_code=500, detail={'error': 'Failed to delete credential'})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/credentials/initialize")
async def initialize_credentials_endpoint():
    """Reload credentials from database."""
    try:
        await initialize_credentials()
        return {
            'success': True,
            'message': 'Credentials reloaded from database'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/database/metrics")
async def database_metrics():
    """Get database metrics and statistics."""
    try:
        supabase_client = get_supabase_client()
        
        # Get various table counts
        tables_info = {}
        
        # Get projects count
        projects_response = supabase_client.table("projects").select("id", count="exact").execute()
        tables_info["projects"] = projects_response.count if projects_response.count is not None else 0
        
        # Get tasks count
        tasks_response = supabase_client.table("tasks").select("id", count="exact").execute()
        tables_info["tasks"] = tasks_response.count if tasks_response.count is not None else 0
        
        # Get crawled pages count
        pages_response = supabase_client.table("crawled_pages").select("id", count="exact").execute()
        tables_info["crawled_pages"] = pages_response.count if pages_response.count is not None else 0
        
        # Get credentials count
        creds_response = supabase_client.table("credentials").select("id", count="exact").execute()
        tables_info["credentials"] = creds_response.count if creds_response.count is not None else 0
        
        return {
            "status": "healthy",
            "database": "supabase",
            "tables": tables_info,
            "total_records": sum(tables_info.values()),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/health")
async def settings_health():
    """Health check for settings API."""
    return {"status": "healthy", "service": "settings"} 