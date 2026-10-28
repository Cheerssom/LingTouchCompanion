# Project handoff

## Repository layout and environment — 2026-10-28

Local October 10–11 handoff content is retained below, with paths updated after merging `claude/trusting-brown-h7384r`. The folder ownership and all entry points are in [README.md](README.md). The remote October 9 handoff remains in [archive/CLAUDE_2026-10-09.md](archive/CLAUDE_2026-10-09.md).

- Shared C++17 code is in `core/`; perception and agent code are in `perception/` and `agent/`; Android and Harmony shells are in `apps/`. The existing paper experiment is in `experiments/chi2027/`. Imported host-test results and untested device/build work are recorded in [the October 28 report](docs/REPORT_2026-10-28.md) and [device checklist](docs/device_tests.md).
- Hardware files are in `hardware/`. The latest PCB1_2 handle entry is the [twist-key handoff](hardware/models/3mf/Handle_TwistKey_2026-10-27/HANDOFF.md), using the retained [October 27 shell source](hardware/models/3mf/Handle_NewPCB_2026-10-20/README.md). The older PCB1_5/Coaxial notes below describe their original drafts; use the newer handle's own handoff for that iteration.
- Vision experiments use `D:/anaconda/envs/LING/python.exe`. The older lowercase `lingtouch` environment has broken NumPy/LAPACK. Experiment scripts honor `LINGTOUCH_ROOT`, then search upward for `.git`.
- Run modelling commands from `hardware/models/`, using `hardware/models/3mf/.runtime/structural-runtime/Scripts/python.exe` from the repository root, or `3mf/.runtime/structural-runtime/Scripts/python.exe` from that working directory. On another machine use the pinned model requirements; do not commit the runtime.
- Keep root `pics/`, `Depth-Anything-V2/`, weights, `experiment_runs/`, `.pcba-workflow/`, secrets, dependencies, paper materials and local archives outside Git. `hardware/models/.pcba-workflow` is a junction to the original root folder. Vendor SDK binaries, disassembly and strings remain local.
- Core build: `cmake -S core -B build/core`, `cmake --build build/core`, then `ctest --test-dir build/core --output-on-failure` (CMake >= 3.16 and a C++17 compiler). Android needs SDK 35, NDK and CMake 3.22.1; Harmony needs DevEco and API 18 / HarmonyOS 5.1.0.
- Do not change the global collaboration contract or local AGENTS memo unless asked.

## Local animation handoff — 2026-10-10

Hsinlung accepted [the JSON playback video](hardware/models/BrailleModule_Video/pin_lift_handoff/out/lingchu_json.mp4) on October 10 and requested a reusable handoff. Next session, read [the pin animation workflow](hardware/models/BrailleModule_Video/PIN_ANIMATION_STATUS_2026-10-10.md). Sending a new JSON authorizes production under these defaults; do not ask again about the already chosen appearance, timing or format. Address him as Hsinlung. PCB notes below remain context for a later PCB request, not a task to start now.

Use the supplied 10×9 binary JSON targets, normally at 500 ms intervals (2 Hz refresh), on the accepted 1086×1448 photo plate at 30 fps. Start all down for 0.5 s, apply the targets, then hold the final settled target for 1 s. Rise is 120–180 ms including delay and settling; fall is 30–60 ms. Only changed states move. A pin that remains raised must not restart its rise, dip or brightness change. Keep fixed per-pin response characteristics with small actuation variation. Preserve the JSON content and timestamps; do not invent patterns or force an extra final clearing operation.

The current entry is [play_json.py](hardware/models/BrailleModule_Video/pin_lift_handoff/play_json.py), using [motion.py](hardware/models/BrailleModule_Video/pin_lift_handoff/motion.py) and the retained photo-pixel generator. Use a distinct output name for each new JSON so the accepted clip is preserved. [JSON_PLAYBACK.md](hardware/models/BrailleModule_Video/pin_lift_handoff/JSON_PLAYBACK.md) records the accepted example and current runner boundaries. The original `step3_render_clip.py` and old motion JSON are historical demonstrations, not the production entry or timing specification. Preserve 07/09/11 and the original references; 10 and 11 are edited illustrations, not independent physical photographs. Heights derived from their highlights and fitted camera are visual settings, not measurements.

## Earlier PCB1_5 handle draft (2026-10-11)

For the retained PCB1_5 handle draft, run `hardware/models/3mf/.runtime/structural-runtime/Scripts/python.exe -B hardware/models/3mf/Handle/check_facts.py` (~5 s). If it prints ALL OK, reuse section A of [hardware/models/3mf/Handle/VERIFIED_FACTS.md](hardware/models/3mf/Handle/VERIFIED_FACTS.md) without re-deriving from the originals; re-derive only on MISMATCH or for new premises. The [October 11 description and fact-check inputs](hardware/models/3mf/Handle/Coaxial_v1/README.md) remain. Its superseded model exports and renders were removed during the authorized cleanup, along with the invalid `Redesign/`, `Concepts/` and posed `GripStudy/` outputs. Those studies placed PCB1_5 2.75 mm off in Z; do not reuse their fit conclusions.

## Read first

- [October 28 engineering report](docs/REPORT_2026-10-28.md), [handoff](docs/plans/HANDOFF_2026-10-28.md) and [device tests](docs/device_tests.md).
- [Latest twist-key handle handoff](hardware/models/3mf/Handle_TwistKey_2026-10-27/HANDOFF.md) and [base shell source](hardware/models/3mf/Handle_NewPCB_2026-10-20/README.md).
- [PCB1_5 handle verified facts](hardware/models/3mf/Handle/VERIFIED_FACTS.md) and [historical coaxial description](hardware/models/3mf/Handle/Coaxial_v1/README.md).
- [Pin animation status and accepted requirements](hardware/models/BrailleModule_Video/PIN_ANIMATION_STATUS_2026-10-10.md): user timing/state decisions, Claude quotations, source roles, code entries, review limits and filed assets.
- [PCB revision package](hardware/pcb/PCB_REDESIGN_2026-10-08/README.txt), its native schematic/PCB files, five schematic images, two placement images and `validation.json`.
- [Manufactured-board audit](hardware/models/3mf/PCB/PCB_PREPOWER_REVIEW_2026-10-07.md): September 15 copper, electrical limits, firmware compatibility and proposed measurements.
- [Array source and tools](hardware/models/BrailleModule_Video/ArrayPreview/README.md): retained unapproved scenes and reusable pattern/video tools; rejected outputs have been removed.
- [Physical and filming references](hardware/models/BrailleModule_Video/inputs/): original module/switch PDFs, physical-module photo/video, prototype A/B photos, and two retained TI filming references. `sources.json` identifies their origins.
- [Selected edited image](image_prompt_comparison_2026-10-10/10_centered_original_scene.png) and its `source.json`; [portable model sources](hardware/models/3mf/README.md).

## October 8–9 PCB drafts: correction still required

The manufactured PCB1_5 and the October redesign are separate evidence. The former has narrow high-current routes, including approximately 0.18 mm on U49 SW to L1. Digital connectivity checks did not establish current capacity. The latest conversation says the manufactured board has no tactile modules and is intended for testing while a replacement is considered. Do not present thermal estimates as measurements or certification.

The October 8 cloud source produced a five-page `Revised_Schematic.epro`, `Actual_Placement.epro2` (191.7065 × 35.7505 mm) and `Test98_Placement.epro2` (98 × 98 mm). Both drafts have 179 components and 1062 connected pin assignments. They are separate saved copies; original PCB1_5 remains. Neither draft has routing or copper pours. Six layers remain: Inner1 GND, Inner4 VCC, four routing layers. Q1's four footprint vias are retained.

Changes include 47 kΩ SER/SRCLK/RCLK pull-downs R40/R41/R42 and optional J_NTC. R22 remains 51 kΩ, with temperature detection disabled; the proposed 100 kΩ/B4100 sensor option would also need R22 changed to 82 kΩ. It is not fitted by default. U48, SW1, J_test and J_NTC retain pads but are excluded from the BOM. The 16-stage HC595/ULN chain, 15 working modules and existing power/gating architecture remain.

The actual-board draft preserves fixed U31–U45/U48 poses and the board outline; ESP sockets keep 25.4 mm spacing. ESP and sockets were rotated together to put the antenna beyond the end. These facts do not establish a practical layout.

**The October 9 follow-up review withdrew the earlier claim that layout optimization was complete. Both boards are drafts needing correction before routing.** It reported:

- U49 feedback-connected R7/R8 pads approximately 9.6/11.5 mm from FB, on the wrong side for a compact feedback arrangement; both drafts reuse this arrangement.
- J1 USB to U53 charger centre distances approximately 53 mm on the actual board and 68 mm on the test board. Review the charging path and local placement.
- Test-board U50/L2 and other power parts remain under ESP, restricting probing, observation and repair despite the larger board.
- ESP underside clearance of at least 4 mm has not been confirmed. Actual module-socket selection, insertion space, screw heads and standoffs are also unresolved. Do not assume ordinary 2.54 mm sockets fit the tactile module.

These are prior inspection findings for Claude to independently check against the files. `validation.json` records net, export and selected geometric checks. Native PCB DRC did not return; no load, temperature, loop or BLE measurements validate these drafts. Empty mismatch lists do not prove physical assembly or power-routing suitability.

Firmware was not changed. The pre-power audit identifies GPIO9/OE polarity and startup-latch ordering incompatibility, and the extra 16th shift stage under the current 15-byte protocol. Review those pending adaptations separately from the schematic; do not claim the new pull-downs resolve them. Preserve U48 as optional. Supplier budgets are 0.17 A per coil (15 groups: 15.3 A on VCC) and approximately 0.08–0.10 A per SMA. These are output-load budgets, not battery current or measured performance.

## Legacy CG attempts and retained sources

Hsinlung rejected the completed 3D video attempts and requested their deletion. The three close-up stills, full frame sequence, videos and associated delivery records were deleted earlier on October 10. Cleanup also removed remaining old overview/switch renders, duplicate archives, temporary downloads/discussions, discarded image intermediates, unused Wood049/NormalGL/MouldDetail assets and obsolete appearance/web reports. The README and video instructions now describe sources and tools only; no approved Cycles deliverable remains.

`image_prompt_comparison_2026-10-10/10_centered_original_scene.png` is the image Hsinlung selected as a starting point for the competition video. It is a generative viewpoint edit of an AI base with four real raised tips composited into it, not an unedited photograph or a simple pixel-preserving perspective correction. Its original prompt and `source.json` are retained. Selection of this starting image does not establish approval of later video output. Do not describe it as experimental photographic evidence.

Original references are consolidated in `hardware/models/BrailleModule_Video/inputs/`; their bytes were preserved. The TI screenshot and excerpt are filming references from another product, not this prototype. Retained source scenes, geometry builders, motion profiles, browser atlases and JSON rendering tools remain available for an explicitly requested next task. In particular, `PhotoStudy/ReferenceStudy.blend` feeds `MotionPreview/build_appearance.py`, and `MotionPreview/AppearanceStudy.blend` feeds `ArrayPreview/build_array.py`. Do not delete these dependencies as disposable renders.

The saved `EnclosedArray.blend` is an unapproved source scene. Its active image textures are the three retained Plastic003 maps; the tabletop is procedural grey. Transmission and pin shadows are enabled, but those settings do not establish convincing translucency or clearly distinguishable raised/retracted states. Historical source-array, enclosure and switch records describe their stated geometric data only. `MotionPreview/AppearanceVerification.json` is also a legacy build input. None is an appearance or physical-assembly approval.

The earlier CG request allowed colour/gloss choices beyond an exact photo match, an installed-button interpretation, and full video generation. Do not restore obsolete restrictions or treat those permissions as appearance approval. Future JSON clips use the accepted photo-pixel workflow above; do not resume or redesign the rejected CG route without a new request.

## Other recent work and environment

- `hardware/models/3mf/` retains front, rear and two-part handle inputs, final files, generators and readback verification. Digital reproduction does not prove physical fit. Do not restore the superseded root model folders.
- `hardware/models/BrailleModule/` is the separate static exterior model; `hardware/models/BrailleModule_Video/` retains the visual/motion sources. Their unmarked geometric details and timing remain estimates. Do not merge or delete these intentional source sets as duplicates.
- The experiment path remains `experiments/chi2027/visionss/experiment_server.py`, shared by spatial and single-point conditions. Logs are ignored; firmware is still V2.8. See the respective READMEs and [experiments/chi2027/TOPDOWN_VALIDATION.md](experiments/chi2027/TOPDOWN_VALIDATION.md) for historical offline evidence. No new camera or experimental validation is implied by this handoff.
- Vision uses `D:/anaconda/envs/LING/python.exe`. The old lowercase `lingtouch` environment has broken NumPy/LAPACK. Modelling uses `hardware/models/3mf/.runtime/structural-runtime/Scripts/python.exe`; on another machine install the pinned modelling/module requirements. Do not commit the runtime.
- `pics/`, `Depth-Anything-V2/`, weights, experiment logs, secrets, dependencies, paper materials and local archives remain outside Git. Preserve those original datasets and user work. Do not update the global collaboration contract or local AGENTS memo unless asked.
