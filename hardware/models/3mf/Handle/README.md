# Manual two-object handle recovery

Current PCB1_2 handle work: [twist-key handoff](../Handle_TwistKey_2026-10-27/HANDOFF.md), using the retained [October 27 shell source](../Handle_NewPCB_2026-10-20/README.md).

For the original PCB1_5 handle, [VERIFIED_FACTS.md](VERIFIED_FACTS.md) and `check_facts.py` remain available. `Coaxial_v1/` retains the supplier input, corrected PCB cache and extraction tool needed by that check. Superseded printable studies, grip poses and review renders were removed; small historical descriptions remain as evidence for the modelling lessons. `GripStudy/` retains the original licensed hand, calibrated neutral rig and reusable hand/contact tools.

`inputs/Handle_Original.3mf` is the unchanged manual source supplied on 2026-10-06.
SHA256: 25cd55ec492a72cccf81dd1d16a50490106574b93a2b63005601ec6ab786d6c6.
`Handle_Print.3mf` contains the original two separately selectable model objects;
no added split plane or new joint is constructed.

Run `python 3mf/Handle/regenerate.py --require-baseline` from `hardware/models/`.
`source.py` resolves the archive's external production-model links and all build
and component transforms. `build.py` recovers each native mesh and print mesh;
`export.py` preserves the whole source archive for an unchanged build. Verification
compares every vertex, triangle, transform and ZIP member, including print settings
and assembly metadata.

The housing has 35,944 vertices and 71,860 triangles. The cover has 329 vertices
and 670 triangles. Both have closed manifold meshes. The housing's original mesh
contains eight constituent solid components; the cover contains one. These
source components are retained exactly, without welding or automatic repairs.
This is an exact recovery of the source model objects, not a new physical
connectivity or manufacturing certification.

For future changes, edit `modify_part()` in `build.py`, using each original native
mesh frame. `--verify` accepts deliberate edits while reporting baseline changes;
`--require-baseline` requires the entire finished archive to remain identical.
