from pydantic import BaseModel, Field


class Dimensions(BaseModel):
    width: int
    height: int


class DesignMetadata(BaseModel):
    frame_name: str
    dimensions: Dimensions
    text_content: list[str] = []
    colors: list[str] = []
    component_names: list[str] = []


class FrameData(BaseModel):
    image: str
    metadata: DesignMetadata


class FeedbackRequest(BaseModel):
    image: str | None = None
    metadata: DesignMetadata | None = None
    frames: list[FrameData] | None = None
    personas: list[str] = Field(min_length=1)
    context: str | None = None
