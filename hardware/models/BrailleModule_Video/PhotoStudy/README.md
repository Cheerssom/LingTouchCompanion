# Module appearance study sources

`ReferenceStudy.blend` and `build.py` retain an editable appearance trial for
the single module. This study has not been accepted for photographic realism
or complete device assembly; the former rendered stills are no longer a
completed delivery.

The source chain is `../BrailleModule.blend` → `build.py` →
`ReferenceStudy.blend`. The builder keeps the source module's separate parts
and retracted dots, then adds trial materials, lighting, a table and two
cameras. Material, lighting and camera choices are visual estimates.

The original supplier drawing and physical-module photograph are in
`../inputs/Braille_Module_Reference.pdf` and `../inputs/Touchpoint_Reference.jpg`.
The [user-provided Dot Pad video](https://www.youtube.com/watch?v=iSmRM2PUBzA)
was an additional photography reference, not a specification for this module.

To rebuild the study from the repository root with the existing Blender
runtime (this also generates trial renders):

```powershell
& '3mf/.runtime/structural-runtime/Scripts/python.exe' -B 'BrailleModule_Video/PhotoStudy/build.py' --final
```

The source model and original references remain separate from the generated
study. Source preservation and numerical checks do not establish resemblance
to the physical module or fit inside the handle.
