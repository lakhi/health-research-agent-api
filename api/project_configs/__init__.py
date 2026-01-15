"""
Project configuration package for multi-project API.

Provides abstract base configuration and concrete implementations for each supported project.
Import the factory function to get the active project configuration:

    from api.project_configs import get_project_config

    config = get_project_config()  # Returns VaxStudyConfig or HealthsocConfig based on PROJECT_NAME env var
"""

from api.project_configs.project_config_base import (
    ProjectName,
    ProjectConfig,
    get_project_config,
)
from api.project_configs.vax_study_config import VaxStudyConfig
from api.project_configs.healthsoc_config import HealthsocConfig

__all__ = [
    "ProjectName",
    "ProjectConfig",
    "get_project_config",
    "VaxStudyConfig",
    "HealthsocConfig",
]
