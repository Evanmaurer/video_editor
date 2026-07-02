from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from montage_backend.models.domain import MontageError, new_uuid, utc_now_iso

MONTAGE_PLAN_SCHEMA_VERSION = 1


class MontagePlanStatus(str, Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    APPLIED = "applied"
    ERROR = "error"
    CANCELLED = "cancelled"


class TransitionType(str, Enum):
    HARD_CUT = "hard_cut"
    FADE = "fade"
    CROSSFADE = "crossfade"
    FLASH = "flash"
    MOTION_BLUR = "motion_blur"
    SPEED_RAMP = "speed_ramp"
    ZOOM = "zoom"
    WHIP = "whip"


class MontageEffectType(str, Enum):
    SPEED_RAMP = "speed_ramp"
    CAMERA_SHAKE = "camera_shake"
    ZOOM_PUNCH = "zoom_punch"
    COLOR_GRADE = "color_grade"
    MOTION_BLUR = "motion_blur"
    GLOW = "glow"
    SHARPEN = "sharpen"
    VIGNETTE = "vignette"


class MontageAudioActionType(str, Enum):
    MUTE = "mute"
    DUCK = "duck"
    BOOST = "boost"
    CROSSFADE = "crossfade"
    SYNC_BEAT = "sync_beat"


class MontageTransition(BaseModel):
    type: TransitionType
    duration_ms: int = Field(ge=0, default=0)
    parameters: dict = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reasoning: str = ""


class MontageEffect(BaseModel):
    id: str
    type: MontageEffectType
    enabled: bool = True
    parameters: dict = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reasoning: str = ""


class MontageAudioAction(BaseModel):
    type: MontageAudioActionType
    start_ms: int | None = None
    end_ms: int | None = None
    level_db: float | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reasoning: str = ""


class BeatAlignment(BaseModel):
    beat_timestamp_ms: int | None = None
    aligned: bool = False
    offset_ms: int = 0
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reasoning: str = ""


class MontagePlanClip(BaseModel):
    id: str
    media_id: str
    order: int = Field(ge=0)
    source_start_ms: int = Field(ge=0)
    source_end_ms: int = Field(ge=0)
    source_start_frame: int | None = Field(default=None, ge=0)
    source_end_frame: int | None = Field(default=None, ge=0)
    timeline_start_ms: int = Field(ge=0)
    timeline_end_ms: int = Field(ge=0)
    clip_score: float = Field(ge=0.0, le=100.0)
    playback_speed: float = Field(gt=0.0, default=1.0)
    transition_in: MontageTransition | None = None
    transition_out: MontageTransition | None = None
    audio_actions: list[MontageAudioAction] = Field(default_factory=list)
    effects: list[MontageEffect] = Field(default_factory=list)
    beat_alignment: BeatAlignment | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class MontagePlanCard(BaseModel):
    type: str
    text: str = ""
    duration_ms: int = Field(ge=0, default=3000)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    reasoning: str = ""


class MontagePlanMusic(BaseModel):
    media_id: str | None = None
    bpm: float | None = None
    beat_markers_ms: list[int] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reasoning: str = ""


class MontagePlanMetadata(BaseModel):
    schema_version: int = MONTAGE_PLAN_SCHEMA_VERSION
    generator_id: str = "montage-plan-framework"
    generator_version: str = "1.0.0"
    random_seed: int = 0
    pacing_profile: str | None = None
    target_duration_ms: int | None = None
    module_outputs: dict[str, dict] = Field(default_factory=dict)
    feedback_preferences: dict = Field(default_factory=dict)


class MontagePlan(BaseModel):
    id: str
    project_id: str
    name: str
    status: MontagePlanStatus
    version: int = Field(ge=1, default=1)
    clips: list[MontagePlanClip] = Field(default_factory=list)
    title_card: MontagePlanCard | None = None
    ending_card: MontagePlanCard | None = None
    music: MontagePlanMusic | None = None
    metadata: MontagePlanMetadata = Field(default_factory=MontagePlanMetadata)
    overall_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    overall_reasoning: str = ""
    duration_ms: int = Field(ge=0, default=0)
    applied_timeline_id: str | None = None
    created_at: str
    updated_at: str


class MontagePlanSummary(BaseModel):
    id: str
    project_id: str
    name: str
    status: MontagePlanStatus
    version: int
    clip_count: int
    duration_ms: int
    overall_confidence: float
    applied_timeline_id: str | None = None
    created_at: str
    updated_at: str


class CreateMontagePlanRequest(BaseModel):
    name: str = "Untitled Montage"
    random_seed: int | None = None
    target_duration_ms: int | None = None
    pacing_profile: str | None = None


class UpdateMontagePlanRequest(BaseModel):
    name: str | None = None
    status: MontagePlanStatus | None = None
    clips: list[MontagePlanClip] | None = None
    title_card: MontagePlanCard | None = None
    ending_card: MontagePlanCard | None = None
    music: MontagePlanMusic | None = None
    overall_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    overall_reasoning: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    applied_timeline_id: str | None = None
    metadata: MontagePlanMetadata | None = None


class MontagePlanNotFoundError(MontageError):
    code = "MONTAGE_PLAN_NOT_FOUND"


class MontagePlanValidationError(MontageError):
    code = "MONTAGE_PLAN_VALIDATION"


class MontagePlanCancelledError(MontageError):
    code = "MONTAGE_PLAN_CANCELLED"


class MontagePlanNotReadyError(MontageError):
    code = "MONTAGE_PLAN_NOT_READY"


def new_montage_plan(
    *,
    project_id: str,
    name: str = "Untitled Montage",
    random_seed: int | None = None,
    target_duration_ms: int | None = None,
    pacing_profile: str | None = None,
) -> MontagePlan:
    now = utc_now_iso()
    seed = random_seed if random_seed is not None else abs(hash(f"{project_id}:{now}")) % (2**31)
    metadata = MontagePlanMetadata(
        random_seed=seed,
        target_duration_ms=target_duration_ms,
        pacing_profile=pacing_profile,
    )
    return MontagePlan(
        id=new_uuid(),
        project_id=project_id,
        name=name,
        status=MontagePlanStatus.DRAFT,
        metadata=metadata,
        created_at=now,
        updated_at=now,
    )


def compute_plan_duration_ms(plan: MontagePlan) -> int:
    if not plan.clips:
        title_ms = plan.title_card.duration_ms if plan.title_card else 0
        ending_ms = plan.ending_card.duration_ms if plan.ending_card else 0
        return title_ms + ending_ms
    clip_end = max(clip.timeline_end_ms for clip in plan.clips)
    ending_ms = plan.ending_card.duration_ms if plan.ending_card else 0
    return clip_end + ending_ms


def validate_montage_plan(plan: MontagePlan) -> None:
    orders = [clip.order for clip in plan.clips]
    if len(orders) != len(set(orders)):
        raise MontagePlanValidationError("Clip order values must be unique")

    for clip in plan.clips:
        if clip.source_end_ms <= clip.source_start_ms:
            raise MontagePlanValidationError(
                f"Clip {clip.id} source_end_ms must be greater than source_start_ms",
            )
        if clip.timeline_end_ms < clip.timeline_start_ms:
            raise MontagePlanValidationError(
                f"Clip {clip.id} timeline_end_ms must be >= timeline_start_ms",
            )


def plan_to_summary(plan: MontagePlan) -> MontagePlanSummary:
    return MontagePlanSummary(
        id=plan.id,
        project_id=plan.project_id,
        name=plan.name,
        status=plan.status,
        version=plan.version,
        clip_count=len(plan.clips),
        duration_ms=plan.duration_ms,
        overall_confidence=plan.overall_confidence,
        applied_timeline_id=plan.applied_timeline_id,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )
