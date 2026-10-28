# JSON target playback

Hsinlung accepted `out/lingchu_json.mp4` on 2026-10-10 and asked to use this method for future JSON videos. This record describes that accepted example and the current runner. The default production instructions are in [the pin animation workflow](../PIN_ANIMATION_STATUS_2026-10-10.md). Sending a new JSON authorizes production under those defaults.

Rerun this example from the package directory using `D:/anaconda/envs/LING/python.exe` and the local FFmpeg:

```
python step1_detect_dots.py    # only if work/grid.npy is missing
python step2_fit_camera.py    # only if work/cam.npz is missing
python play_json.py          # writes out/lingchu_json.*; do not rerun over the accepted copy casually
```

For a later JSON, preserve its bytes in `inputs/` and specify both `--targets inputs/<new-file>.json` and `--name <new-name>`. A unique name preserves the accepted clip and earlier outputs. Reuse the approved base, appearance, motion model and video format. Hold the new final target for 1 s after settling; an all-down ending is a property of this example, not a requirement for future content.

## Scripts

- `motion.py` holds target loading, state changes and pin motion. It works in milliseconds and has no side effects on import.
- `play_json.py` handles sampling at 30 fps, rendering, encoding, the record files and the checks.

`generator.py`, `step3_render_clip.py` and the earlier outputs were not changed.

## Input

The input is `inputs/lingchu_frames_1791643082241.json`. It is a byte-identical copy of Hsinlung's Downloads file (SHA-256 `fc86e84c…df6f6`). It holds 9 targets with timestamps 0–4000 ms in 500 ms steps.

## Accepted example settings

**Timeline**
- All pins start down. The first 500 ms are still.
- Target k is applied at 500 ms + its timestamp.
- After the last movement, the first fully-down frame is held for 30 frames (1 s).
- Total: 167 frames, 5.567 s.

**State changes**
- Only 0→1 starts a rise and only 1→0 starts a fall.
- A pin with an unchanged target gets no event. Its level, and so its pixels, stay fixed.

**Heights**
- Level 1 is the settled raised state. The rendered height is `HOLD` (0.5 mm) × the pin's fixed height factor from `generator.py`.
- Rendered heights are rounded to 0.002 mm.

**Rise**
- A rise lasts 125–175 ms from the target time to settled. This includes the pin's own start delay.
- Shape: a first move, a dip, then settled.
- The dip is placed so that the 30 fps frames catch it.

**Fall**
- A fall lasts 32–58 ms, using a cosine ease.

**Variation**
- Each pin has fixed characteristics: delay (about one pin in six starts 22–30 ms late), first level, dip depth, rise time and fall time. These are seeded by the pin alone.
- Each actuation adds a small random variation, seeded by pin and actuation count.

**Sampling**
- Each frame shows the levels at its start time (i × 1000/30 ms).
- There is no shutter blending, because blending two pin positions draws a double outline.

**Mapping**
- JSON row r and column c map to picture row r (top = 0) and column c (left = 0), unmirrored.
- This matches `ArrayPreview/render_cycles.py` and the accepted example. The JSON file itself does not encode a device-mirroring convention; preserve this display mapping unless Hsinlung requests a change.

**Encoding**
- libx264, CRF 10, yuv420p, 1086×1448, 30 fps.

## Records in `out/`

| File | Content |
|---|---|
| `lingchu_json_events.json` | Source hash, timeline, each pin's fixed characteristics and height factor, and every rise/fall with its parameters, end time and frame position |
| `lingchu_json_frames.csv` | For each frame and each of the 16 moving pins: target, level, and rendered height in mm |
| `lingchu_json_trajectory_ms.npz` | Level of all 90 pins at every millisecond (`t_ms`, `level`), plus `height_factor` and `hold_mm` |
| `lingchu_json_check.json` | Checks below |
| `lingchu_json_review.png`, `lingchu_json_review_zoom.png` | Crops from the decoded video: the whole sequence, and row 4 rising while row 3 holds (frames 29–36) |

## Checks (in `lingchu_json_check.json`)

**Raw frames, before encoding**
- Frames 0–15 are byte-identical to the all-down plate (533 ms), and so are the last 30 frames (1000 ms).
- Every pin that is raised and unchanged across two consecutive frames has identical pixels: 369 checks, maximum difference 0.
- Pixels change only inside the areas of pins whose height changed: 0 frames have stray changes.

**Timing, from the millisecond trajectory**
- All 16 rises settle in 141–169 ms after the target time.
- All 16 falls reach down in 36–54 ms.
- Raised holds stay at level 1.0 until the next fall event.
- The dip shows in the sampled frames for 15 of 16 rises.

**Decoded video**
- 167 frames, 30 fps, FFmpeg return code 0.
- Frames that should be still differ by at most 4 levels. This comes from the encoder.

The numerical checks establish state, timing and pixel stability. Independent decoded adjacent-frame and full-frame review found raised/down states distinguishable and no obvious separated double pinhead, aperture break or held pin overwritten by a neighbour. Codex inspected frames; Hsinlung subsequently accepted the delivered video. Acceptance of this illustration does not establish measured mechanical stroke or photographic authenticity.

Independent exact-duration review found rises of 140.317–168.790 ms and falls of 35.073–53.199 ms. The integer-ms checks above round settling up to the next millisecond. The final movement ends near 4546.362 ms; the first completely down sampled frame is frame 137 at 4566.667 ms. Frames 137–166 provide a complete 1 s final static hold.

## Current runner boundaries

These describe the current code, not additional product requirements. Handle a new input within its production task before encoding; preserve its intended content and complete duration.

- Targets must be a non-empty list of 10×9 binary `frame` arrays with finite, strictly increasing `ts` values in milliseconds. The runner adds 500 ms to the supplied timestamps without normalizing the first timestamp. This accepted export starts at `ts=0`.
- Fixed 2026-10-12 (Claude): the runner no longer requires an all-down ending, accepts a sequence with no state changes, and starts the final 1 s hold at the first frame at or after both the last movement end and the last target time. A rerun of the accepted input under a temporary name reproduced identical frame records, millisecond trajectory and decoded frames (maximum difference 0). Temporary tests ending raised (152 frames, final raised state held 30 frames) and with no movement (60 frames) passed the runner checks and were removed. `<name>_check.json` now reports `end_frames_equal_final` and `final_target_raised`; `start_frames_equal_base` counts only frames before the first target time.
- A reversal before a rise has settled interrupts that motion. Targets at the approved 500 ms cadence avoid this case. If a supplied schedule conflicts with the established cadence, inspect the input before changing it or claiming complete 120–180 ms rises.
- The default name is `lingchu_json`, which overwrites this example. Always use a new name for a new input.
