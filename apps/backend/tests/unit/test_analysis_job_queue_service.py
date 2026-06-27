from __future__ import annotations

from montage_backend.analysis.base import AnalysisModuleId
from montage_backend.models.domain.analysis import AnalysisJobRecord
from montage_backend.models.domain.media import ProcessingStatus
from montage_backend.services.analysis_service import AnalysisService


def test_module_priorities_scene_highest():
    priorities = AnalysisService.MODULE_PRIORITIES
    assert priorities[AnalysisModuleId.SCENE.value] > priorities[AnalysisModuleId.EMBEDDING.value]
    assert priorities[AnalysisModuleId.SCENE.value] > priorities[AnalysisModuleId.MOTION.value]


def test_analysis_job_record_includes_retry_fields():
    job = AnalysisJobRecord(
        id="j1",
        project_id="p1",
        media_id="m1",
        module_id="scene",
        status=ProcessingStatus.PENDING,
        priority=50,
        retry_count=1,
        max_retries=2,
        created_at="t",
        updated_at="t",
    )
    assert job.retry_count == 1
    assert job.max_retries == 2
