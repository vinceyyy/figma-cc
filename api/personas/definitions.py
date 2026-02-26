import json
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from api.config import settings


class Persona(BaseModel):
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
        data = json.loads(json_file.read_text())
        persona = Persona.model_validate(data)
        personas[persona.id] = persona
        logger.debug("Loaded persona: {pid} ({file})", pid=persona.id, file=json_file.name)

    if not personas:
        raise ValueError(f"No persona JSON files found in: {dir_path.resolve()}")

    return personas


# Load personas at import time from configured directory
PERSONAS = load_personas(settings.personas_dir)
logger.info("Loaded {count} personas total", count=len(PERSONAS))


def get_persona(persona_id: str) -> Persona | None:
    return PERSONAS.get(persona_id)


def list_personas() -> list[dict[str, str]]:
    """Return list of {id, label} for all loaded personas (for API response)."""
    return [{"id": p.id, "label": p.label} for p in PERSONAS.values()]
