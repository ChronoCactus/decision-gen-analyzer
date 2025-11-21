"""
LLM Provider Configuration Storage

Manages persistent storage of LLM provider configurations with encrypted credentials.
Providers are stored in JSON format in /app/data/llm_providers.json
"""

import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

from src.config import get_settings
from src.logger import get_logger

logger = get_logger(__name__)


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider"""

    id: str = Field(description="Unique identifier for this provider")
    name: str = Field(description="Display name for the provider")
    provider_type: str = Field(
        description="Type: ollama, openai, openrouter, vllm, llama_cpp, custom"
    )
    base_url: str = Field(description="Base URL for the LLM API")
    model_name: str = Field(description="Model name/identifier")
    api_key_encrypted: Optional[str] = Field(
        default=None, description="Encrypted API key"
    )
    temperature: float = Field(default=0.7, description="Temperature for generation")
    num_ctx: Optional[int] = Field(
        default=None, description="Context window size (Ollama)"
    )
    num_predict: Optional[int] = Field(
        default=None, description="Max tokens to predict"
    )
    is_default: bool = Field(
        default=False, description="Whether this is the default provider"
    )
    is_env_based: bool = Field(
        default=False, description="Whether this comes from environment variables"
    )
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CreateProviderRequest(BaseModel):
    """Request model for creating a new provider"""

    name: str
    provider_type: str
    base_url: str
    model_name: str
    api_key: Optional[str] = None
    temperature: float = 0.7
    num_ctx: Optional[int] = None
    num_predict: Optional[int] = None
    is_default: bool = False


class UpdateProviderRequest(BaseModel):
    """Request model for updating a provider"""

    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    num_ctx: Optional[int] = None
    num_predict: Optional[int] = None
    is_default: Optional[bool] = None


class ProviderResponse(BaseModel):
    """Response model for provider (without encrypted key)"""

    id: str
    name: str
    provider_type: str
    base_url: str
    model_name: str
    has_api_key: bool
    temperature: float
    num_ctx: Optional[int] = None
    num_predict: Optional[int] = None
    is_default: bool
    is_env_based: bool
    created_at: str
    updated_at: str


class CredentialEncryption:
    """Handles encryption and decryption of API credentials"""

    def __init__(self, salt: Optional[str] = None):
        """
        Initialize encryption with a salt.

        Args:
            salt: Encryption salt from env var or default
        """
        self.salt = salt or get_settings().encryption_salt
        # Create a Fernet key from the salt using PBKDF2
        self._key = self._derive_key(self.salt)
        self._fernet = Fernet(self._key)

    def _derive_key(self, salt: str) -> bytes:
        """Derive a Fernet key from the salt"""
        # Use PBKDF2 to derive a 32-byte key
        key_material = hashlib.pbkdf2_hmac(
            "sha256",
            salt.encode("utf-8"),
            b"llm_provider_encryption",  # Fixed application-specific salt
            100000,  # Iterations
            dklen=32,
        )
        # Fernet requires base64-encoded 32-byte key
        return base64.urlsafe_b64encode(key_material)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string"""
        if not plaintext:
            return ""
        encrypted_bytes = self._fernet.encrypt(plaintext.encode("utf-8"))
        return base64.urlsafe_b64encode(encrypted_bytes).decode("utf-8")

    def decrypt(self, encrypted: str) -> str:
        """Decrypt an encrypted string"""
        if not encrypted:
            return ""
        encrypted_bytes = base64.urlsafe_b64decode(encrypted.encode("utf-8"))
        decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
        return decrypted_bytes.decode("utf-8")


class LLMProviderStorage:
    """Manages persistent storage of LLM provider configurations"""

    def __init__(
        self, storage_path: Optional[Path] = None, encryption_salt: Optional[str] = None
    ):
        """
        Initialize provider storage.

        Args:
            storage_path: Path to JSON storage file (default: /app/data/llm_providers.json)
            encryption_salt: Salt for credential encryption
        """
        settings = get_settings()
        if storage_path is None:
            data_dir = Path(settings.adr_storage_path).parent
            storage_path = data_dir / "llm_providers.json"

        self.storage_path = storage_path
        self.encryption = CredentialEncryption(encryption_salt)
        logger.info(f"LLM Provider storage initialized at {self.storage_path}")

    async def _ensure_storage_dir(self):
        """Ensure the storage directory exists"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    async def _load_providers(self) -> Dict[str, LLMProviderConfig]:
        """Load all providers from storage"""
        await self._ensure_storage_dir()

        if not self.storage_path.exists():
            return {}

        try:
            async with aiofiles.open(self.storage_path, "r") as f:
                content = await f.read()
                data = json.loads(content)
                return {
                    provider_id: LLMProviderConfig(**config)
                    for provider_id, config in data.items()
                }
        except Exception as e:
            logger.error(f"Failed to load providers from {self.storage_path}: {e}")
            return {}

    async def _save_providers(self, providers: Dict[str, LLMProviderConfig]):
        """Save all providers to storage"""
        await self._ensure_storage_dir()

        try:
            data = {
                provider_id: config.model_dump()
                for provider_id, config in providers.items()
            }
            async with aiofiles.open(self.storage_path, "w") as f:
                await f.write(json.dumps(data, indent=2))
            logger.info(f"Saved {len(providers)} providers to {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to save providers to {self.storage_path}: {e}")
            raise

    async def list_all(self) -> List[ProviderResponse]:
        """List all providers (without decrypted credentials)"""
        providers = await self._load_providers()
        return [
            ProviderResponse(
                id=config.id,
                name=config.name,
                provider_type=config.provider_type,
                base_url=config.base_url,
                model_name=config.model_name,
                has_api_key=bool(config.api_key_encrypted),
                temperature=config.temperature,
                num_ctx=config.num_ctx,
                num_predict=config.num_predict,
                is_default=config.is_default,
                is_env_based=config.is_env_based,
                created_at=config.created_at,
                updated_at=config.updated_at,
            )
            for config in providers.values()
        ]

    async def get(self, provider_id: str) -> Optional[LLMProviderConfig]:
        """Get a provider by ID with decrypted credentials"""
        providers = await self._load_providers()
        return providers.get(provider_id)

    async def get_decrypted_api_key(self, provider_id: str) -> Optional[str]:
        """Get decrypted API key for a provider"""
        provider = await self.get(provider_id)
        if provider and provider.api_key_encrypted:
            return self.encryption.decrypt(provider.api_key_encrypted)
        return None

    async def create(self, request: CreateProviderRequest) -> ProviderResponse:
        """Create a new provider"""
        providers = await self._load_providers()

        # Generate unique ID
        provider_id = f"provider_{datetime.utcnow().timestamp()}".replace(".", "_")

        # If setting as default, unset other defaults
        if request.is_default:
            for provider in providers.values():
                if not provider.is_env_based:
                    provider.is_default = False

        # Encrypt API key if provided
        api_key_encrypted = None
        if request.api_key:
            api_key_encrypted = self.encryption.encrypt(request.api_key)

        # Create new provider config
        config = LLMProviderConfig(
            id=provider_id,
            name=request.name,
            provider_type=request.provider_type,
            base_url=request.base_url,
            model_name=request.model_name,
            api_key_encrypted=api_key_encrypted,
            temperature=request.temperature,
            num_ctx=request.num_ctx,
            num_predict=request.num_predict,
            is_default=request.is_default,
            is_env_based=False,
        )

        providers[provider_id] = config
        await self._save_providers(providers)

        logger.info(f"Created provider {provider_id}: {request.name}")

        return ProviderResponse(
            id=config.id,
            name=config.name,
            provider_type=config.provider_type,
            base_url=config.base_url,
            model_name=config.model_name,
            has_api_key=bool(config.api_key_encrypted),
            temperature=config.temperature,
            num_ctx=config.num_ctx,
            num_predict=config.num_predict,
            is_default=config.is_default,
            is_env_based=config.is_env_based,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    async def update(
        self, provider_id: str, request: UpdateProviderRequest
    ) -> Optional[ProviderResponse]:
        """Update an existing provider"""
        providers = await self._load_providers()

        if provider_id not in providers:
            return None

        config = providers[provider_id]

        # Don't allow updating env-based providers
        if config.is_env_based:
            logger.warning(f"Attempted to update env-based provider {provider_id}")
            return None

        # Update fields
        if request.name is not None:
            config.name = request.name
        if request.provider_type is not None:
            config.provider_type = request.provider_type
        if request.base_url is not None:
            config.base_url = request.base_url
        if request.model_name is not None:
            config.model_name = request.model_name
        if request.api_key is not None:
            config.api_key_encrypted = self.encryption.encrypt(request.api_key)
        if request.temperature is not None:
            config.temperature = request.temperature
        if request.num_ctx is not None:
            config.num_ctx = request.num_ctx
        if request.num_predict is not None:
            config.num_predict = request.num_predict

        # Handle default flag
        if request.is_default is not None and request.is_default:
            for other_id, other_provider in providers.items():
                if other_id != provider_id and not other_provider.is_env_based:
                    other_provider.is_default = False
            config.is_default = True
        elif request.is_default is False:
            config.is_default = False

        config.updated_at = datetime.utcnow().isoformat()

        await self._save_providers(providers)
        logger.info(f"Updated provider {provider_id}: {config.name}")

        return ProviderResponse(
            id=config.id,
            name=config.name,
            provider_type=config.provider_type,
            base_url=config.base_url,
            model_name=config.model_name,
            has_api_key=bool(config.api_key_encrypted),
            temperature=config.temperature,
            num_ctx=config.num_ctx,
            num_predict=config.num_predict,
            is_default=config.is_default,
            is_env_based=config.is_env_based,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    async def delete(self, provider_id: str) -> bool:
        """Delete a provider"""
        providers = await self._load_providers()

        if provider_id not in providers:
            return False

        config = providers[provider_id]

        # Don't allow deleting env-based providers
        if config.is_env_based:
            logger.warning(f"Attempted to delete env-based provider {provider_id}")
            return False

        del providers[provider_id]
        await self._save_providers(providers)
        logger.info(f"Deleted provider {provider_id}")
        return True

    async def get_default(self) -> Optional[ProviderResponse]:
        """Get the default provider"""
        providers = await self._load_providers()

        # First check for user-set default
        for config in providers.values():
            if config.is_default:
                return ProviderResponse(
                    id=config.id,
                    name=config.name,
                    provider_type=config.provider_type,
                    base_url=config.base_url,
                    model_name=config.model_name,
                    has_api_key=bool(config.api_key_encrypted),
                    temperature=config.temperature,
                    num_ctx=config.num_ctx,
                    num_predict=config.num_predict,
                    is_default=config.is_default,
                    is_env_based=config.is_env_based,
                    created_at=config.created_at,
                    updated_at=config.updated_at,
                )

        # Fall back to env-based default
        for config in providers.values():
            if config.is_env_based:
                return ProviderResponse(
                    id=config.id,
                    name=config.name,
                    provider_type=config.provider_type,
                    base_url=config.base_url,
                    model_name=config.model_name,
                    has_api_key=bool(config.api_key_encrypted),
                    temperature=config.temperature,
                    num_ctx=config.num_ctx,
                    num_predict=config.num_predict,
                    is_default=config.is_default,
                    is_env_based=config.is_env_based,
                    created_at=config.created_at,
                    updated_at=config.updated_at,
                )

        return None

    async def ensure_env_provider(self):
        """Ensure the env-based provider exists in storage"""
        settings = get_settings()
        providers = await self._load_providers()

        # Check if env-based provider already exists
        env_provider = None
        for config in providers.values():
            if config.is_env_based:
                env_provider = config
                break

        # Create or update env-based provider
        if env_provider:
            # Update existing
            env_provider.provider_type = settings.llm_provider
            env_provider.base_url = settings.llm_base_url
            env_provider.model_name = settings.llm_model
            env_provider.temperature = settings.llm_temperature
            env_provider.num_ctx = settings.ollama_num_ctx
            env_provider.num_predict = settings.ollama_num_predict
            env_provider.updated_at = datetime.utcnow().isoformat()
        else:
            # Create new
            provider_id = "env_default"
            env_provider = LLMProviderConfig(
                id=provider_id,
                name="Environment Default",
                provider_type=settings.llm_provider,
                base_url=settings.llm_base_url,
                model_name=settings.llm_model,
                temperature=settings.llm_temperature,
                num_ctx=settings.ollama_num_ctx,
                num_predict=settings.ollama_num_predict,
                is_default=True,
                is_env_based=True,
            )
            providers[provider_id] = env_provider

        await self._save_providers(providers)
        logger.info("Ensured env-based provider exists in storage")


# Singleton instance
_storage: Optional[LLMProviderStorage] = None


def get_provider_storage() -> LLMProviderStorage:
    """Get the singleton provider storage instance"""
    global _storage
    if _storage is None:
        _storage = LLMProviderStorage()
    return _storage
