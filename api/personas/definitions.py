import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Persona:
    id: str
    label: str
    system_prompt: str


def load_personas(directory: str | Path) -> dict[str, Persona]:
    """Load all persona JSON files from a directory.

    Each JSON file must have: id, label, system_prompt.
    Returns dict keyed by persona id.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Personas directory not found: {dir_path.resolve()}")

    personas: dict[str, Persona] = {}
    for json_file in sorted(dir_path.glob("*.json")):
        with open(json_file) as f:
            data = json.load(f)
        persona = Persona(
            id=data["id"],
            label=data["label"],
            system_prompt=data["system_prompt"],
        )
        personas[persona.id] = persona
        logger.info("Loaded persona: %s (%s)", persona.id, json_file.name)

    if not personas:
        raise ValueError(f"No persona JSON files found in: {dir_path.resolve()}")

    return personas


# Load personas at import time from configured directory
from api.config import settings

PERSONAS = load_personas(settings.personas_dir)


def get_persona(persona_id: str) -> Persona | None:
    return PERSONAS.get(persona_id)


def list_personas() -> list[dict[str, str]]:
    """Return list of {id, label} for all loaded personas (for API response)."""
    return [{"id": p.id, "label": p.label} for p in PERSONAS.values()]
