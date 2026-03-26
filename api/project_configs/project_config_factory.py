import os

from api.project_configs.nex_config import NexConfig
from api.project_configs.project_config import ProjectConfig, ProjectName
from api.project_configs.vax_study_config import VaxStudyConfig


def get_project_config() -> ProjectConfig:
    """
    Factory function to get project configuration based on PROJECT_NAME env var.

    Returns:
        ProjectConfig instance for the active project

    Raises:
        ValueError: If PROJECT_NAME is missing or invalid
    """
    project = os.getenv("PROJECT_NAME")

    if not project:
        raise ValueError(
            f"PROJECT_NAME environment variable must be set. Valid values: {', '.join([p.value for p in ProjectName])}"
        )

    if project == ProjectName.VAX_STUDY.value:
        return VaxStudyConfig()
    elif project == ProjectName.NEX.value:
        return NexConfig()
    else:
        raise ValueError(
            f"Invalid PROJECT_NAME: '{project}'. Must be one of: {', '.join([p.value for p in ProjectName])}"
        )
