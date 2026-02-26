import json

import pytest

from api.personas.definitions import PERSONAS, get_persona, list_personas, load_personas


@pytest.fixture
def persona_dir(tmp_path):
    """Create a temporary directory with test persona JSON files."""
    p1 = {"id": "tester", "label": "Tester", "system_prompt": "You test things."}
    p2 = {"id": "reviewer", "label": "Reviewer", "system_prompt": "You review things."}
    (tmp_path / "tester.json").write_text(json.dumps(p1))
    (tmp_path / "reviewer.json").write_text(json.dumps(p2))
    return tmp_path


def test_load_personas_from_directory(persona_dir):
    personas = load_personas(persona_dir)
    assert len(personas) == 2
    assert "tester" in personas
    assert "reviewer" in personas
    assert personas["tester"].label == "Tester"
    assert len(personas["tester"].system_prompt) > 0


def test_load_personas_missing_dir():
    with pytest.raises(FileNotFoundError, match="Personas directory not found"):
        load_personas("/nonexistent/path")


def test_load_personas_empty_dir(tmp_path):
    with pytest.raises(ValueError, match="No persona JSON files found"):
        load_personas(tmp_path)


def test_default_personas_loaded():
    """The module-level PERSONAS should have loaded from personas/ directory."""
    assert len(PERSONAS) >= 5
    expected = {"first_time_user", "power_user", "accessibility_advocate", "brand_manager", "skeptical_customer"}
    assert expected.issubset(set(PERSONAS.keys()))


def test_get_persona_valid():
    persona = get_persona("first_time_user")
    assert persona is not None
    assert persona.id == "first_time_user"
    assert persona.label == "First-Time User"
    assert len(persona.system_prompt) > 50


def test_get_persona_invalid():
    assert get_persona("nonexistent") is None


def test_list_personas():
    result = list_personas()
    assert isinstance(result, list)
    assert len(result) >= 5
    ids = {p["id"] for p in result}
    assert "first_time_user" in ids
    # Should NOT expose system_prompt
    assert all("system_prompt" not in p for p in result)
