Historical description only. Superseded model files, renders and case-specific tools were removed on 2026-10-28; the text remains as evidence for Shell_Lessons. Current work: ../../Handle_TwistKey_2026-10-27/HANDOFF.md.

【2026-10-11 更正】本文件夹的 PCB 摆位在宽度方向偏了 2.75 mm（用了借来的排母占位模型对齐），据此得出的“PCB 偏向 −Z”、电容让位、定位榫位置等结论不再成立。核实结果见 ../VERIFIED_FACTS.md；当前设计见 ../Coaxial_v1/。

HANDLE ARCHITECTURE CONCEPTS — 2026-10-11

Purpose: explore different handle shapes and internal arrangements while keeping
the existing PCB outline and component layout. These are discussion models.

A_InclinedGrip: a long upper circuit pod, tilted 25 degrees toward the right thumb, with a
separate narrow inclined oval grip. The front bridge stops before the index
finger region. Two cells move into the cane neck.

B_SideReading: the complete PCB and tactile plane rotate 60 degrees toward the
right hand. A narrow side grip separates finger wrap from the wide board. The
empty upper side skirt is shaped closer to the actual component envelope.

C_TGripSpine: the long PCB follows the cane axis. Two short transverse grip arms
join the central spine around the board. The array remains on the front face;
the negative-Z arm is used for the current right-hand study. Cells sit behind
the circuit spine. The arms move forward to X15 instead of making the hand wrap
the circuit spine. The grip-adjacent walls follow the actual board envelope.

DELIVERABLES
Handle_Concepts.blend contains all three full-geometry concepts, with collections
offset by 0, 380 and 760 mm for comparison. Each concept has its own camera.
The parent assembly tool adds the editable right-hand study collections.
Each concept folder contains Overview.png, concept.json and millimetre NPZ
meshes. concept_index.json lists all parts and proper rigid transformations.
The interactive viewer uses reduced outer meshes and measured individual
component-box occupancy; full STEP-derived surfaces remain in the Blender file.

RETAINED HARDWARE
Source: ../../PCB/3D_PCB1_5_2026-09-15_no_U31-U45_U48_headers.step.
PCB bare size: 191.681 x 35.725 x 1.538 mm. All 157 face-bearing components are
tessellated and moved together without reflection. The source also has six empty
copper/silkscreen/stiffener nodes, listed in PCB_RigidReference.json.
Two P28A envelopes: diameter 18.6 mm, length 65.2 mm. Cane socket bore: 25 mm.
The 15 tactile bodies and 90 raised points are dimensional/schematic envelopes;
their final socket and pin-to-PCB relationship is not established by this model.
The roof and adjoining array frame meet the fixed tactile face at canonical
Y23.5; raised points extend to Y24. Windows pass through the entire shell and
support bridges, avoiding an artificial recess or a hidden bridge membrane.

CHECKED SCOPE
spatial_checks.json checks rigid-source vertex preservation, structural contact,
and interference against each retained component's measured bounding box. The
union of each concept's shells, bars and socket has one connected positive-volume
body. Enclosed cavities appear as negative-volume surface components.
Hand studies have separate source hashes, pose/contact results and views.

No print joint, strength, final fastening, protection-board package, wiring,
ESP devboard body, socket insertion or human comfort approval is implied.
Original handle inputs and earlier Redesign/GripStudy deliverables are preserved.

HAND REFERENCE
Emma L. D. Lieker, anatomical-hand-model:
https://github.com/emmalieker/anatomical-hand-model
CC BY-NC 4.0; original licence and source remain in ../GripStudy/inputs/.
The source left hand is reflected as a complete rig/skin/nail assembly to make
the right hand, followed only by proper rigid rotations for each concept.
Generic adult calibration: wrist-to-middle fingertip 180 mm, palm breadth 78 mm.
The 21-bone FK rig remains editable. This is a posture/space study, not a
person-specific hand model or evidence of comfort for a real participant.

REUSABLE TOOLS
The frozen editable right-hand rigs have been merged into Handle_Concepts.blend.
assembly_readback.json confirms that evaluated skin in the merged project agrees
with each frozen hand study to less than 0.001 mm after removing its display offset.

Pose limits: A still has weak palm support and about 1.46 mm of local thumb-root
overlap with the housing. B has about 1.72 mm of local index-root overlap at its
front bridge. These are retained concept-study limitations, not approved hand
clearances. C's final full-skin union check found no overlap. Static thumb contact
does not establish sweep access to all fifteen modules or real-user comfort.

build_concepts.py rebuilds the shell concepts and source PCB cache.
build_view_occupancy.py builds compact per-component occupancy for the viewer.
check_spatial_concepts.py runs the narrow structural and layout checks above.
