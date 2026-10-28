# Module motion preview sources

This folder retains editable single-module scenes and a keyboard-controlled
browser preview. Its appearance and motion have not been accepted for
photographic realism or complete device assembly; the former rendered stills
and render reports are no longer a completed delivery.

The source chain is:

- `../PhotoStudy/ReferenceStudy.blend` → `build_appearance.py` →
  `AppearanceStudy.blend`.
- `AppearanceStudy.blend` and `assets/motion.json` → `build_motion.py` →
  `ModuleMotion.blend`.
- `AppearanceStudy.blend` → `render_assets.py` → the browser's retained
  background, dot atlases and manifest in `assets/`.

`AppearanceVerification.json` is retained because `build_motion.py` reads it.
It records legacy source-change checks; its pass fields do not certify visual
quality or physical assembly. The browser atlases are reusable preview assets,
not evidence of an accepted render.

## Browser controls

Run `launch.cmd`, then open <http://127.0.0.1:8866/> in Chrome or Edge. Click the
picture to focus it and press **1–6**, numeric keypad keys, or the six buttons.
Each control raises its dot to a peak, settles it to a maintained height, and
retracts it on the next press. **全部收回** retracts all dots; **显示编号** shows
their positions. Held keys do not repeatedly toggle a dot.

The browser selects a rendered height sample for each dot. The Blender scene
provides editable axial motion using the same `assets/motion.json` profile.

| Stage | Provisional height / duration |
| --- | --- |
| Retracted | 0 mm |
| Rise | 33 ms, reaching 0.70 mm |
| High peak pause | 67 ms |
| Settle | 50 ms, reaching 0.45 mm |
| Maintained | 0.45 mm, until toggled off |
| Retract | 50 ms |

These values are preview choices, not measured manufacturer specifications.
The requested peak-to-hold sequence is not established quantitatively by the
physical reference video (`../inputs/PhysicalMotionReference.mp4`, 30 fps).
Camera movement, compression and frame rate limit what can be inferred about
stroke height, timing and any intermediate drop.

## Editable timeline

`ModuleMotion.blend` retains a 60 fps sample timeline (frames 1–430): each dot
rises in turn, all remain raised, then all retract. Select the root object
**BrailleModule** for `Dot_1_height_mm` through `Dot_6_height_mm` under Object
Properties → Custom Properties; edit their curves in the Graph Editor.

The single-module sources do not verify the 15-module array, handle openings,
PCB placement, clearances or complete installed device. Numerical source and
motion checks supplement visual review; they do not replace it.
