# JSON video jobs

The rendered results were rejected by Hsinlung and deleted. The retained source scene and tools are unapproved; these instructions describe the interface, not an approved appearance or deliverable.

## Entry and output

Run from the repository root:

```powershell
& './BrailleModule_Video/ArrayPreview/GenerateVideo.ps1' './BrailleModule_Video/ArrayPreview/video.example.json' -Validate
```

`-Validate` checks input structure, timeline bounds and expected frame count without rendering. Remove it to render. The retained Blender Python includes the encoder. The tool loads `EnclosedArray.blend`, uses its saved materials and lighting, and does not save scene changes.

By default each run creates a folder under `%TEMP%/LingTouchVideo`, containing `video.mp4`, PNG frames, `resolved_job.json` and `run.json`. `-Out 'C:/path/my-video'` selects a folder. Resume requires matching inputs, source scene, textures and generator revision; conflicting existing outputs are rejected.

[video.example.json](video.example.json) uses the saved five-second timeline. [video.patterns.example.json](video.patterns.example.json) supplies custom target events. They are operation examples.

## Cameras and quality

`shots` is an ordered edit list. Each entry selects `near`, `switch` or `whole` and a source interval `[start_s, end_s)` in seconds. Whole 0–1 s followed by near 1–5 s produces a five-second video. Repeating an interval with another camera is supported. If omitted, `shots` uses `near` for the full timeline.

Optional `near_elevation_deg` changes a near camera in memory; optional `fstop` changes its focus range. Other camera settings come from the saved scene.

`render` accepts even `width`/`height`, integer `fps`, `samples`, `device` (`auto`, `cpu`, `gpu`) and `deduplicate_holds`. Defaults are 1920×1080, saved-scene FPS, 128 samples, automatic device selection and hold reuse. Changing output FPS samples the animation at the corresponding times without changing source motion keys.

Hold reuse requires all 90 pins to stay stationary throughout the motion-blur shutter interval. Matching pose, camera and render settings can reuse a PNG; moving frames are rendered. Grain is added separately to each encoded frame. `run.json` records `rendered`, `reused` or `resumed` for every frame.

## Target events

Use `"timeline": "reference"` for the saved timeline, or supply custom events:

```json
"timeline": {
  "events": [
    {"time_s": 0, "pattern": "off"},
    {"time_s": 1, "pattern": "checker"},
    {"time_s": 2, "pattern": "cross"},
    {"time_s": 3, "pattern": "on"},
    {"time_s": 4, "pattern": "off"}
  ],
  "tail_s": 1
}
```

Times are seconds in ascending order. Events set target states using the saved peak, hold, rise, settle and retraction profile. Repeating the same target does not restart a stroke; reversals begin at the current height. Custom keys exist only in memory. If the first event occurs after zero, the array starts off.

`pattern` accepts `off`, `checker`, `cross`, `on`, 10 strings of 9 bits, or a 10×9 matrix of 0/1. Rows and columns follow the editor from top to bottom and left to right. **1 raises a pin; 0 retracts it.** Each two rows and three columns form one six-dot module. M1–M15 run left to right, then top to bottom; each module's upper row is dots 3/2/1 and lower row is 6/5/4.

## Browser-exported sequences

The editor's exported sequence also works directly: a record list, `{ "frames": [...] }`, JSONL, one record or a single 10×9 matrix. Its `ts` timestamps are milliseconds. The tool uses the near camera for the full sequence and adds a one-second tail. Invalid cells and decreasing timestamps are rejected.

Input validation, frame records, motion comparisons and source-preservation checks do not establish visual realism, raised/retracted visibility or assembly fit. Review actual images and complete assembly evidence for those questions. Source maintenance is documented in [README.md](README.md); Chinese instructions are in [使用说明.md](使用说明.md).
