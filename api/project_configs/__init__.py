"""
Project configuration package for multi-project API.

Provides abstract base configuration and concrete implementations for each supported project.
Import the factory function to get the active project configuration:

    from api.project_configs import get_project_config

    config = get_project_config()  # Returns VaxStudyConfig or NexConfig based on PROJECT_NAME env var
"""

from api.project_configs.nex_config import NexConfig
from api.project_configs.project_config import (
    ProjectConfig,
    ProjectName,
)
from api.project_configs.project_config_factory import get_project_config
from api.project_configs.ssc_psych_config import SscPsychConfig
from api.project_configs.vax_study_config import VaxStudyConfig

__all__ = [
    "ProjectName",
    "ProjectConfig",
    "get_project_config",
    "VaxStudyConfig",
    "NexConfig",
    "SscPsychConfig",
]
