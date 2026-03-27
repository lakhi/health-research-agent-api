import logging
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic_settings import BaseSettings

from api.project_configs import ProjectConfig, get_project_config
from api.project_configs.project_config import ProjectName

# Budget timezone constant (hardcoded, not configurable)
BUDGET_TIMEZONE = "Europe/Vienna"

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

    # Budget configuration for nex_agent
    daily_budget_eur: Optional[float] = None
    model_pricing_input_eur: Optional[float] = None
    model_pricing_output_eur: Optional[float] = None

    # u:Cloud (Nextcloud) configuration for nex_agent research papers
    ucloud_share_token: Optional[str] = None
    ucloud_share_password: str = ""

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

    @model_validator(mode="after")
    def validate_nex_budget_settings(self):
        """Require budget env vars only for nex project."""
        if self.project_config.project_name != ProjectName.NEX.value:
            return self

        missing_vars = []
        if self.daily_budget_eur is None:
            missing_vars.append("DAILY_BUDGET_EUR")
        if self.model_pricing_input_eur is None:
            missing_vars.append("MODEL_PRICING_INPUT_EUR")
        if self.model_pricing_output_eur is None:
            missing_vars.append("MODEL_PRICING_OUTPUT_EUR")
        if not self.ucloud_share_token:
            missing_vars.append("UCLOUD_SHARE_TOKEN")

        if missing_vars:
            missing = ", ".join(missing_vars)
            raise ValueError(f"Missing required budget environment variables for PROJECT_NAME=nex: {missing}")

        return self

    @property
    def project_config(self) -> ProjectConfig:
        """Get the active project configuration."""
        return get_project_config()


# Create ApiSettings object
api_settings = ApiSettings()
