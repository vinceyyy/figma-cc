from api.models.request import FeedbackRequest, DesignMetadata, Dimensions, FrameData
from api.models.response import Annotation, FeedbackResponse, PersonaFeedback, Issue


def test_feedback_request_valid():
    req = FeedbackRequest(
        image="aGVsbG8=",  # base64 "hello"
        metadata=DesignMetadata(
            frame_name="Login",
            dimensions=Dimensions(width=1440, height=900),
            text_content=["Sign In"],
            colors=["#ffffff"],
            component_names=["Button"],
        ),
        personas=["first_time_user"],
        context="A login page",
    )
    assert req.personas == ["first_time_user"]


def test_feedback_request_no_context():
    req = FeedbackRequest(
        image="aGVsbG8=",
        metadata=DesignMetadata(
            frame_name="Login",
            dimensions=Dimensions(width=1440, height=900),
        ),
        personas=["first_time_user"],
    )
    assert req.context is None


def test_persona_feedback_model():
    fb = PersonaFeedback(
        persona="first_time_user",
        persona_label="First-Time User",
        overall_impression="Looks clean.",
        issues=[
            Issue(
                severity="high",
                area="CTA",
                description="Button is too small",
                suggestion="Make it bigger",
            )
        ],
        positives=["Good color scheme"],
        score=7,
    )
    assert fb.score == 7
    assert len(fb.issues) == 1


def test_annotation_model_percentage():
    ann = Annotation(
        x_pct=10.5,
        y_pct=20.0,
        width_pct=30.0,
        height_pct=15.0,
        issue_index=0,
        label="Navigation",
    )
    assert ann.x_pct == 10.5
    assert ann.issue_index == 0


def test_persona_feedback_with_annotations():
    fb = PersonaFeedback(
        persona="first_time_user",
        persona_label="First-Time User",
        overall_impression="Looks clean.",
        issues=[
            Issue(severity="high", area="CTA", description="Button is too small", suggestion="Make it bigger")
        ],
        positives=["Good color scheme"],
        score=7,
        annotations=[
            Annotation(x_pct=50.0, y_pct=80.0, width_pct=20.0, height_pct=10.0, issue_index=0, label="CTA"),
        ],
    )
    assert len(fb.annotations) == 1
    assert fb.annotations[0].label == "CTA"


def test_annotation_with_frame_index():
    ann = Annotation(
        frame_index=2,
        x_pct=10.0,
        y_pct=20.0,
        width_pct=30.0,
        height_pct=15.0,
        issue_index=0,
        label="Button",
    )
    assert ann.frame_index == 2


def test_annotation_default_frame_index():
    ann = Annotation(
        x_pct=10.0,
        y_pct=20.0,
        width_pct=30.0,
        height_pct=15.0,
        issue_index=0,
        label="Button",
    )
    assert ann.frame_index == 0


def test_frame_data_model():
    fd = FrameData(
        image="aGVsbG8=",
        metadata=DesignMetadata(
            frame_name="Login",
            dimensions=Dimensions(width=1440, height=900),
        ),
    )
    assert fd.metadata.frame_name == "Login"


def test_feedback_request_with_frames():
    req = FeedbackRequest(
        frames=[
            FrameData(
                image="aGVsbG8=",
                metadata=DesignMetadata(
                    frame_name="Step 1",
                    dimensions=Dimensions(width=1440, height=900),
                ),
            ),
            FrameData(
                image="aGVsbG8=",
                metadata=DesignMetadata(
                    frame_name="Step 2",
                    dimensions=Dimensions(width=1440, height=900),
                ),
            ),
        ],
        personas=["first_time_user"],
    )
    assert len(req.frames) == 2
    assert req.image is None


def test_feedback_request_single_still_works():
    req = FeedbackRequest(
        image="aGVsbG8=",
        metadata=DesignMetadata(
            frame_name="Login",
            dimensions=Dimensions(width=1440, height=900),
        ),
        personas=["first_time_user"],
    )
    assert req.image == "aGVsbG8="
    assert req.frames is None


def test_feedback_response_model():
    resp = FeedbackResponse(
        feedback=[
            PersonaFeedback(
                persona="first_time_user",
                persona_label="First-Time User",
                overall_impression="Nice.",
                issues=[],
                positives=[],
                score=8,
            )
        ]
    )
    assert len(resp.feedback) == 1
