# Photo based pin animation workflow

Updated 2026-10-10. Hsinlung accepted [lingchu_json.mp4](pin_lift_handoff/out/lingchu_json.mp4) and authorized this workflow for later JSON files. A new JSON from him is a request to produce its video using the defaults below. Do not restart the route discussion or ask again about approved timing, appearance or format.

His acceptance and next-session instruction:

> “我觉得没啥问题，你可以准备总结了，后续我就直接给你发json然后开始做了”

Read [the playback record](pin_lift_handoff/JSON_PLAYBACK.md), inspect the new input, and use [play_json.py](pin_lift_handoff/play_json.py), [motion.py](pin_lift_handoff/motion.py) and [generator.py](pin_lift_handoff/generator.py). Preserve the accepted example and original material. The original [Claude HANDOFF](pin_lift_handoff/HANDOFF.md) remains source documentation; its older undecided timing and demo behavior are superseded here.

## Default production settings

| Setting | Default |
|---|---|
| Content | The supplied JSON targets, without invented scan patterns |
| Grid | 10 rows × 9 columns, binary 0/1; top row and left column are index 0, without mirroring |
| Appearance | Existing photo-pixel generator and fixed 1086×1448 base |
| Video | 1086×1448, 30 fps, H.264, yuv420p, CRF 10 |
| Start | All pins down for 500 ms; targets applied at 500 ms + JSON `ts` |
| Cadence | Normally 500 ms per target, interpreted as 2 Hz refresh |
| Rise | 120–180 ms including start delay, visible dip and settling |
| Fall | 30–60 ms |
| End | Hold the final target after movement has settled for at least 1 s; do not add an unrequested clearing target |
| Pin identity | Fixed per-pin surface and response characteristics, with only small variation between actuations |

Only 0→1 rises and 1→0 falls. A 1→1 target keeps the existing raised pin unchanged; 0→0 stays down. Two refreshes per second do not force every pin to pulse twice. With alternating targets, a complete up/down cycle takes 1 s.

The user selected these animation timings, rather than measuring mechanical tolerances:

> “我们取升起大约120-180ms，落下大约30-60ms，这个频率，然后每秒两次”

> “原本就凸起的点就不会额外有动作了”

Keep the current rise–dip–settle shape and restrained per-pin differences. Do not restore the unsupported 0.7 mm overshoot followed by a 0.45 mm plateau. JSON 1 means a settled raised state, not 1 mm. `HOLD=0.5` is a visual height setting multiplied by the fixed per-pin height factor exactly once; it is not a duration or a measured physical stroke.

## Producing the next JSON video

1. Preserve the supplied JSON bytes in `pin_lift_handoff/inputs/`, with its source path and hash in the playback record. Check dimensions, binary values, timestamps and target changes. Inspect genuine inconsistencies before interpreting them; do not silently change content or speed.
2. Reuse `work/grid.npy` and `work/cam.npz`. Run `step1_detect_dots.py` and `step2_fit_camera.py` only if the cache is missing or the base changes. Use the existing LING environment and FFmpeg.
3. Choose a distinct output name based on the new input. Run `play_json.py --targets inputs/<new-file>.json --name <new-name>` from the package directory. The default name would overwrite the accepted example, so always specify a new name.
4. Check the rendered result and its state/timing records, then deliver the actual MP4 inline. Keep the input, reusable code, final video and useful review records; remove only self-created temporary or superseded outputs.

Runtime: `D:/anaconda/envs/LING/python.exe`, Python 3.11, NumPy 2.4.4, SciPy 1.17.1, OpenCV 5.0.0 and local FFmpeg 9.0.1 have run this workflow successfully. Use this environment rather than the broken lowercase `lingtouch` environment. Encoder versions can change decoded pixels; do not require byte-identical MP4s across environments.

On 2026-10-12 the runner was fixed to hold a raised final target, accept input without movement and keep the last timestamp before the 1 s hold; the accepted example reproduced identically. Remaining input boundaries are listed in [JSON_PLAYBACK.md](pin_lift_handoff/JSON_PLAYBACK.md). An implementation restriction must not become a new user requirement. Do not impose an all-down ending or truncate timestamps to make a new input fit the old example.

## What to review before delivery

State and timing checks must agree with the actual JSON: only changed pins start new movements; already raised pins keep their settled level and local pixels; movements stay within the selected duration ranges; the complete target sequence and final 1 s hold remain in the video. Decode the delivered MP4 to verify its dimensions, frame count and timing.

Inspect raised/down endpoints, neighbouring moving and held pins, and adjacent frames around rises and falls. Look for disconnected cap/shaft layers, double contours, aperture seams, a moving neighbour overwriting a held pin, changing static pin identity, and a dip lost between samples. Review the complete frame at the delivered size. Checks on hashes, output validity or background preservation do not establish convincing appearance. State whether the review used decoded adjacent frames or original-speed continuous playback.

The accepted example uses one sampled instant per frame, with the visible dip wide enough to survive 30 fps sampling. Shutter averaging was removed because blending different positions drew a double outline. Do not reintroduce it without judging the actual encoded result.

## Accepted example and evidence

Input: [lingchu_frames_1791643082241.json](pin_lift_handoff/inputs/lingchu_frames_1791643082241.json), 9 targets at 0–4000 ms in 500 ms steps. Output: [lingchu_json.mp4](pin_lift_handoff/out/lingchu_json.mp4), 167 frames, 5.5667 s. SHA-256: `6cf6a3b4756da065b88e35919604a58b662e685be3b48485a460483b59809840`.

The sequence moves a 2×2 group down columns 6/7, eventually leaving only the final row before clearing. Sixteen different pins each rise once and fall once. Commands start at 0.5 s; first visible motion is the next sampled frame at 0.533 s. The last motion ends near 4.546 s; the final 30 fully-down frames cover 4.5667–5.5667 s.

Independent review found rise durations of 140.317–168.790 ms and fall durations of 35.073–53.199 ms, with no repeated actuation for unchanged targets. Frame records and the 1 ms trajectory agreed with independently calculated values. The raw renderer's 369 held-pin checks had zero difference; encoded still frames differed by at most 4/255 per channel. This distinction matters: do not claim the lossy video is pixel-identical during every hold.

Decoded adjacent-frame and full-frame review found distinguishable rise/down states and no obvious separated double pinhead, aperture break or held pin overwritten by its neighbour. Codex's inspection was frame based. Hsinlung's subsequent acceptance approves this example and the future production defaults; it does not validate physical millimetres or turn the edited base into an experimental photograph. See [the detailed checks](pin_lift_handoff/out/lingchu_json_check.json) and [playback record](pin_lift_handoff/JSON_PLAYBACK.md).

## Claude method and source limits

Claude's forwarded explanation:

> “每个点用它自己落下时的像素生成升起的样子；往哪挪、挪多少、变多大，由相机角度和针头尺寸算。”

> “顶部像素整体上移（高光跟着走，不缩放），外圈补出原来藏着的一圈，提亮约24%（从那四个点量的），挪开后露出的孔补暗。”

The generator moves the central texture without scaling it, continues the rim, fills the exposed hole and adjusts brightness. Baseline brightness gain is 1.24. Static differences are fixed by pin; the original demo randomized the whole response on each rise. The current `motion.py` implements the agreed correction:

> “同一根针的快慢不该每次换。改成每根针固定的响应差异、每次只小幅波动，改 `profile()` 一个函数就行，位置我在代码和交接里标了。”

The fixed differences and small actuation variation are chosen visual settings. Real footage has too few repeated actuations of the same pin to establish a persistent mechanical response for each pin.

[Prototype A](inputs/PrototypeSurface_A.jpeg), [Prototype B](inputs/PrototypeSurface_B.jpeg) and [single-module close-up](inputs/Touchpoint_Reference.jpg) are physical appearance references. [PhysicalMotionReference.mp4](inputs/PhysicalMotionReference.mp4) is the handheld prototype movement reference: 720×1280, 30 fps, 342 frames, 11.4 s. The rises near 2.3/8.5 s show an initial rise, brief reduction in raised appearance and further settling; the fall is near 10 s. The appearance score in [the rhythm sheet](pin_lift_handoff/review/real_video_rhythm.png) is not measured height. Approximate visual rise/fall timings from that footage were 170–200/30–70 ms; the user's newer animation ranges take precedence.

Claude withdrew the one-frame-rise claim:

> “升起不是一帧切完：先弹到七八成，第三帧掉回一半左右，再用两三帧爬到位。”

[07](../image_prompt_comparison_2026-10-10/07_selected_all_down.png) is the edited/AI base; [09](../image_prompt_comparison_2026-10-10/09_real_pin_composite.png) and [its provenance](../image_prompt_comparison_2026-10-10/09_real_pin_provenance.json) add four real tips; [10](../image_prompt_comparison_2026-10-10/10_centered_original_scene.png) is a generative viewpoint edit of that composite, described in [source.json](../image_prompt_comparison_2026-10-10/source.json). [11](../image_prompt_comparison_2026-10-10/11_all_down_same_module.png) replaces four corners with same-row middle-pin patches, described in [its source record](../image_prompt_comparison_2026-10-10/11_all_down_same_module_source.json). It is not an independent all-down photograph. Their pixel comparison found 8,881 changed pixels inside four 53-pixel circular patches; [check_10_vs_11.py](pin_lift_handoff/check_10_vs_11.py) reproduces the comparison. Package 10/11 inputs have the same decoded pixels as these originals; its physical video is byte-identical.

The 90-centre camera fit has roughly 0.60 px RMS and 1.89 px worst coordinate residual. It establishes an approximate fit to the edited picture, not real-camera calibration or physical vertical displacement. Claude's correction remains applicable:

> “0.45–0.65 mm 不能算实测，它说得对，我那条作废。同理，‘每升高 1 mm 挪多少像素’也只是调节值……所以我拟合的相机只代表这张图自洽。”

These animations are edited illustrations. Do not use them as unedited prototype photographs or performance measurements in a paper. Independent raised targets for other rows and cast shadows were not added; changing the base, viewpoint or pixel dimensions requires new appearance review.

## Preservation and legacy material

Keep restored 07/09/11, original physical references, source scenes, the original Claude scripts/HANDOFF, earlier comparison clips and the accepted output. The user's ZIP was extracted and checked before its Downloads original was removed as requested; earlier comparison assets were moved to `pin_lift_handoff/review/`. The varied full-raised plate and varied demo remain in `out/`; the older uniform plate remains in `review/`.

The original `step3_render_clip.py` is a legacy demonstration: its schedule, per-event random response and 40–70 ms falls are superseded by the production entry. Importing it renders immediately; do not import it for review. Old `MotionPreview`/`ArrayPreview` motion JSON with 0.7→0.45 mm and a 33 ms rise is not the current specification. Original-source preservation does not require using those stale defaults.

The shaft branch activates above approximately 0.46 mm in `generator.py`; do not repeat the old claim that it is unused. Review its actual pixels if height or appearance is changed. Claude's eight generator pitfalls and exact code locations remain in [HANDOFF.md](pin_lift_handoff/HANDOFF.md). The [TI macro excerpt](inputs/TI_82-95s_Pin_Macro_Refresh.mp4) and [screenshot](inputs/TI_DotPad_085s.png) are filming references from another product.

The rejected full-CG route stays out of the JSON workflow. No Git commit, unrelated cleanup, PCB edit or global contract change is authorized by this summary.
