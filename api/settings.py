import logging
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic_settings import BaseSettings

from api.project_configs import get_project_config, ProjectConfig

# Load environment variables before instantiating settings
load_dotenv()

# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ApiSettings(BaseSettings):
    cors_origin_list: Optional[List[str]] = Field(None, validate_default=True)

    @field_validator("cors_origin_list", mode="before")
    def set_cors_origin_list(cls, cors_origin_list, info: FieldValidationInfo):
        # Get project-specific CORS origins
        project_config = get_project_config()

        valid_cors = cors_origin_list or []

        # Add app.agno.com to cors to allow requests from the Agno playground.
        valid_cors.append("https://app.agno.com")
        # Add localhost to cors to allow requests from the local environment.
        valid_cors.append("http://localhost")
        # Add localhost:3000 to cors to allow requests from local Agent UI.
        valid_cors.append("http://localhost:3000")

        # Add project-specific CORS origins
        valid_cors.extend(project_config.cors_origins)

        return valid_cors

    @property
    def project_config(self) -> ProjectConfig:
        """Get the active project configuration."""
        return get_project_config()


# Create ApiSettings object
api_settings = ApiSettings()
