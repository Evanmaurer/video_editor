from __future__ import annotations

from fastapi import APIRouter, Depends

from montage_backend.api.deps import get_llm_service, get_project_service, get_settings_service
from montage_backend.models.domain import AiFeatureStatus, AppSettings, GpuInfo, LlmProviderConfig
from montage_backend.services.llm_service import LlmService
from montage_backend.services.project_service import AppSettingsService, ProjectService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=AppSettings)
async def get_settings(
    service: AppSettingsService = Depends(get_settings_service),
) -> AppSettings:
    return await service.get_settings()


@router.put("", response_model=AppSettings)
async def update_settings(
    updates: AppSettings,
    settings_service: AppSettingsService = Depends(get_settings_service),
    llm: LlmService = Depends(get_llm_service),
) -> AppSettings:
    saved = await settings_service.update_settings(updates.model_dump())
    await llm.configure(saved.llm)
    return saved


@router.get("/gpu", response_model=GpuInfo)
async def get_gpu_info(
    project_service: ProjectService = Depends(get_project_service),
    settings_service: AppSettingsService = Depends(get_settings_service),
) -> GpuInfo:
    app_settings = await settings_service.get_settings()
    return project_service.get_gpu_info(app_settings.gpu_enabled)


@router.get("/ai-status", response_model=AiFeatureStatus)
async def get_ai_status(
    llm: LlmService = Depends(get_llm_service),
) -> AiFeatureStatus:
    return await llm.get_status()


@router.get("/llm/providers")
async def list_llm_providers() -> dict[str, list[str]]:
    return {
        "providers": ["ollama", "openai", "none"],
        "recommended_local_models": [
            "qwen3:8b-instruct",
            "llama3.2:3b",
        ],
    }
