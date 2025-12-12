from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic_settings import BaseSettings


class ApiSettings(BaseSettings):
    cors_origin_list: Optional[List[str]] = Field(None, validate_default=True)

    @field_validator("cors_origin_list", mode="before")
    def set_cors_origin_list(cls, cors_origin_list, info: FieldValidationInfo):
        valid_cors = cors_origin_list or []

        # Add app.agno.com to cors to allow requests from the Agno playground.
        valid_cors.append("https://app.agno.com")
        # Add localhost to cors to allow requests from the local environment.
        valid_cors.append("http://localhost")
        # Add localhost:3000 to cors to allow requests from local Agent UI.
        valid_cors.append("http://localhost:3000")

        # Add Marhinovirus Study UI Agent
        valid_cors.append(
            "https://marhinovirus-study-ui.whitedesert-10483e06.westeurope.azurecontainerapps.io"
        )
        # Add HRN Agent UI
        valid_cors.append(
            "https://hrn-agent-ui.niceground-23078755.westeurope.azurecontainerapps.io"
        )

        return valid_cors


# Create ApiSettings object
api_settings = ApiSettings()
