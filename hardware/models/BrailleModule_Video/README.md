# Braille module animation and sources

Hsinlung accepted the [photo-based JSON playback video](pin_lift_handoff/out/lingchu_json.mp4) on October 10. Future JSON files use [the current animation workflow](PIN_ANIMATION_STATUS_2026-10-10.md): the supplied targets, a 0.5 s initial hold, 500 ms target cadence, state-preserving pin motion and a 1 s final settled hold, at 1086×1448 and 30 fps. Sending a new JSON authorizes production with these defaults.

Start with [play_json.py](pin_lift_handoff/play_json.py) and [JSON_PLAYBACK.md](pin_lift_handoff/JSON_PLAYBACK.md); use a distinct output name for each input. [Claude's original HANDOFF](pin_lift_handoff/HANDOFF.md) retains generator details and source limitations. The original demonstration and rejected full-CG attempts are separate from this accepted workflow; failed CG outputs were removed and their source scenes remain available.

## Source chain

- `BrailleModule.blend`, `.glb`, `.step`, `build.py`, `parameters.json` and `requirements.txt`: retained static exterior source. The separate `../BrailleModule/` source set remains intentional.
- [PhotoStudy](PhotoStudy/README.md): the retained `ReferenceStudy.blend` used to construct the motion appearance source.
- [MotionPreview](MotionPreview/README.md): retained editable six-pin motion scene, browser controls, required pose atlases and provisional motion profile.
- [ArrayPreview](ArrayPreview/README.md): retained 15-module/90-pin source scenes, offline pattern editor and JSON rendering tools. Their appearance is unapproved.
- `inputs/`: unchanged module/switch PDFs, physical-module photo/video, prototype photographs, and two third-party filming references. `sources.json` distinguishes their origins.
- [Selected starting image](../../../image_prompt_comparison_2026-10-10/10_centered_original_scene.png): an AI/composited image selected for the competition video, with its original prompt and provenance record. It is not an unedited photograph.

Keep source dependencies and the linked Plastic003 textures together. Geometric reconstruction, motion checks and successful file export do not establish physical stroke or PCB/enclosure assembly fit. New JSON clips use the accepted photo-pixel route; retained CG scenes are not an instruction to restart that route.
