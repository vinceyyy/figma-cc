from api.personas.definitions import PERSONAS, get_persona


def test_all_personas_exist():
    expected = {"first_time_user", "power_user", "accessibility_advocate", "brand_manager", "skeptical_customer"}
    assert set(PERSONAS.keys()) == expected


def test_get_persona_valid():
    persona = get_persona("first_time_user")
    assert persona.id == "first_time_user"
    assert persona.label == "First-Time User"
    assert len(persona.system_prompt) > 50  # Has meaningful content


def test_get_persona_invalid():
    persona = get_persona("nonexistent")
    assert persona is None
