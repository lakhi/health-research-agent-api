from enum import Enum


class AgentType(Enum):
    def __init__(self, id: str, name: str):
        self._id = id
        self._name = name

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    HEALTHSOC_CHATBOT = ("healthsoc_chatbot", "Health in Society Chatbot")
    CONTROL_MARHINOVIRUS = ("control_agent", "Control Marhinovirus Agent")
    SIMPLE_LANGUAGE_MARHINOVIRUS = (
        "simple_lg_agent",
        "Simple Language Marhinovirus Agent",
    )
    SIMPLE_CATALOG_LANGUAGE_MARHINOVIRUS = (
        "simple_catalog_lg_agent",
        "Simple Catalog and Language Marhinovirus Agent",
    )
