from enum import Enum


class HrnMembers(Enum):
    """Enum of Health Research Network members with their metadata."""

    ROBERT = (
        "Robert Böhm",
        "https://ucrisportal.univie.ac.at/en/persons/robert-b%C3%B6hm",
    )
    JANINA = (
        "Janina Meillan-Kehr",
        "https://ucrisportal.univie.ac.at/en/persons/janina-meillan-kehr",
    )
    JULIA = (
        "Julia Reiter",
        "https://ucrisportal.univie.ac.at/en/persons/julia-reiter",
    )
    VERONIKA = (
        "Veronika Siegl",
        # ucris portal not updated
        "https://orcid.org/0000-0002-1973-5467",
    )

    def __init__(self, member_name: str, ucris_url: str):
        self.member_name = member_name
        self.ucris_url = ucris_url

    def to_metadata(self) -> dict:
        """Convert to metadata dictionary for knowledge base."""
        return {
            "network_member_name": self.member_name,
            "network_meber_ucris_url": self.ucris_url,
        }
