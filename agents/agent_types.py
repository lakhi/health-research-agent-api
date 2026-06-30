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

    HEX_GIG_AGENT = ("hex", "Health Explorer (GiG)")
    SSC_PSYCH_AGENT = ("ssc", "SSC Psychologie Assistant")
    CONTROL_MARHINOVIRUS = ("c", "Agent C")
    SIMPLE_LANGUAGE_MARHINOVIRUS = ("sl", "Agent SL")
