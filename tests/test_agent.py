from api.agents.persona_agent import build_feedback_schema
from api.models.response import PersonaFeedback


def test_build_feedback_schema():
    schema = build_feedback_schema()
    assert schema["type"] == "json_schema"
    assert "schema" in schema
    # The schema should define the PersonaFeedback structure
    props = schema["schema"]["properties"]
    assert "overall_impression" in props
    assert "issues" in props
    assert "score" in props


def test_feedback_schema_includes_annotations():
    schema = build_feedback_schema()
    ann_schema = schema["schema"]["properties"]["annotations"]
    # annotations should allow a list of Annotation objects
    # Check that the Annotation schema has percentage fields
    defs = schema["schema"].get("$defs", {})
    assert "Annotation" in defs
    ann_props = defs["Annotation"]["properties"]
    assert "x_pct" in ann_props
    assert "issue_index" in ann_props


def test_persona_feedback_schema_roundtrip():
    """Verify that PersonaFeedback JSON schema can validate a sample response."""
    sample = {
        "persona": "first_time_user",
        "persona_label": "First-Time User",
        "overall_impression": "Looks good.",
        "issues": [
            {
                "severity": "high",
                "area": "CTA",
                "description": "Button too small",
                "suggestion": "Make bigger",
            }
        ],
        "positives": ["Nice colors"],
        "score": 7,
        "annotations": None,
    }
    fb = PersonaFeedback.model_validate(sample)
    assert fb.score == 7
