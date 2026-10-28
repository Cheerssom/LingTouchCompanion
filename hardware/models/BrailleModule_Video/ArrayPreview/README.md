# Array preview and rendering tools

The rendered results were rejected by Hsinlung and deleted. This directory retains unapproved source scenes, the pattern editor and rendering tools. There is no approved visual deliverable. A successful render or preservation check does not establish acceptable appearance or physical assembly fit.

## Retained files

- `EnclosedArray.blend`: saved enclosure and 15-module, 90-pin scene for Cycles.
- `ModuleArray.blend`, `build_array.py`, `surface_finish.py`: source array and its construction tools.
- `index.html`: offline 10-row × 9-column pattern editor and approximate interactive preview.
- `assets/sequence.json`, `assets/motion.json`: saved target sequence and motion settings.
- `GenerateVideo.ps1`, `generate_video.py`: JSON-to-video entry that loads the saved scene without saving changes to it.
- `render_cycles.py`: scene preparation, still rendering, sequence rendering and animation checks.

Keep the scene with its linked files under `assets/textures/`. These textures and the saved material parameters remain unapproved visual choices. The browser preview does not establish the appearance of a Cycles render or control real hardware.

## Pattern editing and video jobs

Open `index.html`, edit or import a 10 × 9 pattern sequence, then choose **导出 JSON**. `launch.cmd` can serve the editor at `http://127.0.0.1:8867/`.

Run from the repository root. Check a job without rendering:

```powershell
& './BrailleModule_Video/ArrayPreview/GenerateVideo.ps1' './BrailleModule_Video/ArrayPreview/video.patterns.example.json' -Validate
```

The rendering entry uses the same command without `-Validate`:

```powershell
& './BrailleModule_Video/ArrayPreview/GenerateVideo.ps1' './BrailleModule_Video/ArrayPreview/video.patterns.example.json'
```

[video.patterns.example.json](video.patterns.example.json) demonstrates custom target events. [video.example.json](video.example.json) uses the saved reference timeline. Both are operation examples, not reviewed outputs. Browser-exported JSON or JSONL can also be supplied directly.

Each run writes a video, PNG frames and an execution record to its own folder under `%TEMP%/LingTouchVideo`. Use `-Out 'C:/path/my-video'` to select a folder. An interrupted job can resume only with matching inputs and scene revision. See [VIDEO_JSON.md](VIDEO_JSON.md) for patterns, cameras, quality and output handling, or [使用说明.md](使用说明.md) for Chinese instructions.

## Scene maintenance

Use the retained runtime from the repository root:

```powershell
# Update and save appearance while preserving saved pin motion; no render.
& '3mf/.runtime/structural-runtime/Scripts/python.exe' -B 'BrailleModule_Video/ArrayPreview/render_cycles.py' prepare --appearance-only

# Update appearance and render a still for review; this also saves the scene.
& '3mf/.runtime/structural-runtime/Scripts/python.exe' -B 'BrailleModule_Video/ArrayPreview/render_cycles.py' stills --appearance-only --shot near --out 'C:/path/review'

# Import a browser sequence and rebuild motion before rendering a review still.
& '3mf/.runtime/structural-runtime/Scripts/python.exe' -B 'BrailleModule_Video/ArrayPreview/render_cycles.py' stills --sequence 'C:/path/frames.json' --shot near --out 'C:/path/review'
```

`--appearance-only` preserves saved pin curves, rest positions and timeline; it cannot be combined with `--sequence`. Without it, preparation regenerates motion from the supplied sequence or `assets/sequence.json`. `--out` changes the still-output folder; it does not prevent scene saving.

`--shot near|switch|whole|all` selects cameras. `--width`, `--height`, `--samples`, `--frame` and `--near-elevation` select still settings. The JSON video entry supports camera and timeline changes in memory and leaves the source scene unsaved.

`build_enclosure.py` is for an intentional geometry rebuild. Browser source files are `viewer3d.js`, `controls.js` and `index.template.html`; `npm run build` regenerates the self-contained page. `node build_web.mjs --page-only` updates embedded page assets while reusing the viewer bundle.

## Verification limits

`-Validate` checks input structure, timeline bounds and expected frame count. Animation checks compare the browser and Blender motion, pin indexing and fractional-frame heights. Preservation checks compare mesh data, transforms or saved curves. Execution records identify inputs and rendered, reused or resumed frames.

These checks do not evaluate resemblance to the real parts, raised/retracted visibility, material realism, PCB mounting, enclosure clearances or physical assembly. Those results need evidence from the actual images and the relevant complete assembly before any approval claim.
