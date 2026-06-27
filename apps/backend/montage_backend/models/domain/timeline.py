from __future__ import annotations

from pydantic import BaseModel, Field

from montage_backend.models.domain import MontageError, new_uuid, utc_now_iso


class TimelineNotFoundError(MontageError):
    code = "TIMELINE_NOT_FOUND"
    status_code = 404


class TimelineDocument(BaseModel):
    """Timeline document persisted as JSON on disk."""

    id: str
    project_id: str
    name: str = "Main"
    version: int = 1
    settings: dict = Field(default_factory=dict)
    duration_ms: int = 0
    tracks: list[dict] = Field(default_factory=list)
    markers: list[dict] = Field(default_factory=list)
    beat_markers: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str


class TimelineSummary(BaseModel):
    id: str
    project_id: str
    name: str
    duration_ms: int
    is_active: bool
    version: int
    updated_at: str


class SaveTimelineResponse(BaseModel):
    id: str
    version: int
    updated_at: str


class CreateTimelineRequest(BaseModel):
    name: str = "Main"


def default_timeline_document(
    *,
    project_id: str,
    width: int,
    height: int,
    frame_rate: float,
    name: str = "Main",
) -> TimelineDocument:
    now = utc_now_iso()
    timeline_id = new_uuid()
    video1 = new_uuid()
    video2 = new_uuid()
    audio1 = new_uuid()
    music = new_uuid()
    return TimelineDocument(
        id=timeline_id,
        project_id=project_id,
        name=name,
        version=1,
        settings={
            "width": width,
            "height": height,
            "frame_rate": frame_rate,
            "sample_rate": 48000,
        },
        duration_ms=0,
        tracks=[
            {
                "id": video1,
                "type": "video",
                "name": "Video 1",
                "index": 0,
                "muted": False,
                "locked": False,
                "visible": True,
                "volume": 1.0,
                "clips": [],
            },
            {
                "id": video2,
                "type": "video",
                "name": "Video 2",
                "index": 1,
                "muted": False,
                "locked": False,
                "visible": True,
                "volume": 1.0,
                "clips": [],
            },
            {
                "id": audio1,
                "type": "audio",
                "name": "Audio 1",
                "index": 2,
                "muted": False,
                "locked": False,
                "visible": True,
                "volume": 1.0,
                "clips": [],
            },
            {
                "id": music,
                "type": "audio",
                "name": "Music",
                "index": 3,
                "muted": False,
                "locked": False,
                "visible": True,
                "volume": 1.0,
                "clips": [],
            },
        ],
        markers=[],
        beat_markers=[],
        metadata={},
        created_at=now,
        updated_at=now,
    )
