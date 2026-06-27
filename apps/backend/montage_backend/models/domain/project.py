from pydantic import BaseModel, Field


class ProjectSettings(BaseModel):
    auto_analyze_on_import: bool = True
    auto_generate_timeline: bool = False
    auto_save_interval_ms: int = 60000
