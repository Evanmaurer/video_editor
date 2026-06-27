import type {
  TimelineDocument,
  TimelineSettings,
  TimelineTrack,
  TrackType,
} from "@montage/shared-types";
import { newId } from "./utils";

export function createDefaultTracks(): TimelineTrack[] {
  const specs: Array<{ type: TrackType; name: string }> = [
    { type: "video", name: "Video 1" },
    { type: "video", name: "Video 2" },
    { type: "audio", name: "Audio 1" },
    { type: "audio", name: "Music" },
  ];

  return specs.map((spec, index) => ({
    id: newId("track"),
    type: spec.type,
    name: spec.name,
    index,
    muted: false,
    locked: false,
    visible: true,
    volume: 1,
    clips: [],
  }));
}

export function createEmptyTimelineDocument(
  projectId: string,
  settings: TimelineSettings,
  name = "Main",
): TimelineDocument {
  const now = new Date().toISOString();
  return {
    id: newId("timeline"),
    project_id: projectId,
    name,
    version: 1,
    settings,
    duration_ms: 0,
    tracks: createDefaultTracks(),
    markers: [],
    beat_markers: [],
    metadata: {},
    created_at: now,
    updated_at: now,
  };
}

export function projectSettingsToTimelineSettings(project: {
  width: number;
  height: number;
  frame_rate: number;
}): TimelineSettings {
  return {
    width: project.width,
    height: project.height,
    frame_rate: project.frame_rate,
    sample_rate: 48000,
  };
}
