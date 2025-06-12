"""
Credential management service for Archon backend

Handles loading, storing, and accessing credentials with encryption for sensitive values.
Credentials include API keys, service credentials, and application configuration.
"""

import os
import re
import base64
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from supabase import create_client, Client
import asyncio
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

@dataclass
class CredentialItem:
    """Represents a credential/setting item."""
    key: str
    value: Optional[str] = None
    encrypted_value: Optional[str] = None
    is_encrypted: bool = False
    category: Optional[str] = None
    description: Optional[str] = None

class CredentialService:
    """Service for managing application credentials and configuration."""
    
    def __init__(self):
        self._supabase: Optional[Client] = None
        self._cache: Dict[str, Any] = {}
        self._cache_initialized = False
        
    def _get_supabase_client(self) -> Client:
        """
        Get or create a properly configured Supabase client using environment variables.
        Uses a robust initialization pattern to ensure project ID is correctly included.
        """
        if self._supabase is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_KEY")
            
            if not url or not key:
                raise ValueError(
                    "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables"
                )
            
            # Extract project ID from URL (required for proper initialization)
            try:
                match = re.match(r'https://([^.]+)\.supabase\.co', url)
                if match:
                    project_id = match.group(1)
                    # Initialize with proper headers including project reference and authorization
                    self._supabase = create_client(
                        url, 
                        key,
                        headers={
                            "X-Client-Info": "archon-credential-service",
                            "apikey": key,
                            "Authorization": f"Bearer {key}"
                        }
                    )
                    logger.info(f"Supabase client initialized for project: {project_id}")
                else:
                    logger.warning(f"Could not extract project ID from URL: {url}")
                    # Fall back to basic initialization
                    self._supabase = create_client(url, key)
            except Exception as e:
                logger.error(f"Error configuring Supabase client: {e}")
                # Fall back to basic initialization (may not work with settings table)
                self._supabase = create_client(url, key)
        
        return self._supabase
    
    def _get_encryption_key(self) -> bytes:
        """Generate encryption key from environment variables."""
        # Use Supabase service key as the basis for encryption key
        service_key = os.getenv("SUPABASE_SERVICE_KEY", "default-key-for-development")
        
        # Generate a proper encryption key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'static_salt_for_credentials',  # In production, consider using a configurable salt
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(service_key.encode()))
        return key
    
    def _encrypt_value(self, value: str) -> str:
        """Encrypt a sensitive value using Fernet encryption."""
        if not value:
            return ""
        
        try:
            fernet = Fernet(self._get_encryption_key())
            encrypted_bytes = fernet.encrypt(value.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encrypting value: {e}")
            raise
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a sensitive value using Fernet encryption."""
        if not encrypted_value:
            return ""
        
        try:
            fernet = Fernet(self._get_encryption_key())
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode('utf-8'))
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Error decrypting value: {e}")
            raise
    
    async def load_all_credentials(self) -> Dict[str, Any]:
        """Load all credentials from database and cache them."""
        try:
            supabase = self._get_supabase_client()
            
            # Fetch all credentials
            result = supabase.table("settings").select("*").execute()
            
            credentials = {}
            for item in result.data:
                key = item["key"]
                if item["is_encrypted"] and item["encrypted_value"]:
                    # For encrypted values, we store the encrypted version
                    # Decryption happens when the value is actually needed
                    credentials[key] = {
                        "encrypted_value": item["encrypted_value"],
                        "is_encrypted": True,
                        "category": item["category"],
                        "description": item["description"]
                    }
                else:
                    # Plain text values
                    credentials[key] = item["value"]
            
            self._cache = credentials
            self._cache_initialized = True
            logger.info(f"Loaded {len(credentials)} credentials from database")
            
            return credentials
            
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            raise
    
    async def get_credential(self, key: str, default: Any = None, decrypt: bool = True) -> Any:
        """Get a credential value by key."""
        if not self._cache_initialized:
            await self.load_all_credentials()
        
        value = self._cache.get(key, default)
        
        # If it's an encrypted value and we want to decrypt it
        if isinstance(value, dict) and value.get("is_encrypted") and decrypt:
            encrypted_value = value.get("encrypted_value")
            if encrypted_value:
                try:
                    return self._decrypt_value(encrypted_value)
                except Exception as e:
                    logger.error(f"Failed to decrypt credential {key}: {e}")
                    return default
        
        return value
    
    async def get_encrypted_credential_raw(self, key: str) -> Optional[str]:
        """Get the raw encrypted value for a credential (without decryption)."""
        if not self._cache_initialized:
            await self.load_all_credentials()
        
        value = self._cache.get(key)
        if isinstance(value, dict) and value.get("is_encrypted"):
            return value.get("encrypted_value")
        
        return None
    
    async def set_credential(self, key: str, value: str, is_encrypted: bool = False, 
                           category: str = None, description: str = None) -> bool:
        """Set a credential value."""
        try:
            supabase = self._get_supabase_client()
            
            if is_encrypted:
                encrypted_value = self._encrypt_value(value)
                data = {
                    "key": key,
                    "encrypted_value": encrypted_value,
                    "value": None,
                    "is_encrypted": True,
                    "category": category,
                    "description": description
                }
                # Update cache with encrypted info
                self._cache[key] = {
                    "encrypted_value": encrypted_value,
                    "is_encrypted": True,
                    "category": category,
                    "description": description
                }
            else:
                data = {
                    "key": key,
                    "value": value,
                    "encrypted_value": None,
                    "is_encrypted": False,
                    "category": category,
                    "description": description
                }
                # Update cache with plain value
                self._cache[key] = value
            
            # Upsert to database with proper conflict handling
            result = supabase.table("settings").upsert(
                data, 
                on_conflict="key"  # Specify the unique column for conflict resolution
            ).execute()
            
            logger.info(f"Successfully {'encrypted and ' if is_encrypted else ''}stored credential: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting credential {key}: {e}")
            return False
    
    async def delete_credential(self, key: str) -> bool:
        """Delete a credential."""
        try:
            supabase = self._get_supabase_client()
            
            result = supabase.table("settings").delete().eq("key", key).execute()
            
            # Remove from cache
            if key in self._cache:
                del self._cache[key]
            
            logger.info(f"Successfully deleted credential: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting credential {key}: {e}")
            return False
    
    async def get_credentials_by_category(self, category: str) -> Dict[str, Any]:
        """Get all credentials for a specific category."""
        if not self._cache_initialized:
            await self.load_all_credentials()
        
        try:
            supabase = self._get_supabase_client()
            result = supabase.table("settings").select("*").eq("category", category).execute()
            
            credentials = {}
            for item in result.data:
                key = item["key"]
                if item["is_encrypted"]:
                    credentials[key] = {
                        "encrypted_value": item["encrypted_value"],
                        "is_encrypted": True,
                        "description": item["description"]
                    }
                else:
                    credentials[key] = item["value"]
            
            return credentials
            
        except Exception as e:
            logger.error(f"Error getting credentials for category {category}: {e}")
            return {}
    
    async def list_all_credentials(self) -> List[CredentialItem]:
        """Get all credentials as a list of CredentialItem objects (for Settings UI)."""
        try:
            supabase = self._get_supabase_client()
            result = supabase.table("settings").select("*").execute()
            
            credentials = []
            for item in result.data:
                cred = CredentialItem(
                    key=item["key"],
                    value=item["value"] if not item["is_encrypted"] else None,
                    encrypted_value="***" if item["is_encrypted"] and item["encrypted_value"] else None,
                    is_encrypted=item["is_encrypted"],
                    category=item["category"],
                    description=item["description"]
                )
                credentials.append(cred)
            
            return credentials
            
        except Exception as e:
            logger.error(f"Error listing credentials: {e}")
            return []
    
    def get_config_as_env_dict(self) -> Dict[str, str]:
        """
        Get configuration as environment variable style dict.
        Note: This returns plain text values only, encrypted values need special handling.
        """
        if not self._cache_initialized:
            # Synchronous fallback - load from cache if available
            logger.warning("Credentials not loaded, returning empty config")
            return {}
        
        env_dict = {}
        for key, value in self._cache.items():
            if isinstance(value, dict) and value.get("is_encrypted"):
                # Skip encrypted values in env dict - they need to be handled separately
                continue
            else:
                env_dict[key] = str(value) if value is not None else ""
        
        return env_dict

# Global instance
credential_service = CredentialService()

async def get_credential(key: str, default: Any = None) -> Any:
    """Convenience function to get a credential."""
    return await credential_service.get_credential(key, default)

async def set_credential(key: str, value: str, is_encrypted: bool = False, 
                        category: str = None, description: str = None) -> bool:
    """Convenience function to set a credential."""
    return await credential_service.set_credential(key, value, is_encrypted, category, description)

async def initialize_credentials() -> None:
    """Initialize the credential service by loading all credentials and setting environment variables."""
    await credential_service.load_all_credentials()
    
    # Set critical credentials as environment variables for child processes
    critical_credentials = [
        "OPENAI_API_KEY",
        "HOST", 
        "PORT",
        "TRANSPORT",
        "MODEL_CHOICE",
        "USE_CONTEXTUAL_EMBEDDINGS",
        "CONTEXTUAL_EMBEDDINGS_MAX_WORKERS",
        "USE_HYBRID_SEARCH", 
        "USE_AGENTIC_RAG",
        "USE_RERANKING"
    ]
    
    for key in critical_credentials:
        try:
            value = await credential_service.get_credential(key, decrypt=True)
            if value:
                os.environ[key] = str(value)
                logger.info(f"Set environment variable: {key}")
        except Exception as e:
            logger.warning(f"Failed to set environment variable {key}: {e}")
    
    logger.info("✅ Credentials loaded and environment variables set") 
