"""Tessellate every component of the retained PCB1_5 STEP separately, in the handle frame
(X length, Y up, Z width) with the corrected lateral pose (+2.75 mm Z vs Codex). Board
height is NOT applied here (Codex board top = -0.1). Writes pcb_parts.npz + pcb_parts.json."""
from pathlib import Path
import json
import numpy as np
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_Label
from OCP.collections import Sequence_TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopoDS import TopoDS
from OCP.TopLoc import TopLoc_Location
from OCP.IFSelect import IFSelect_RetDone

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / 'PCB' / '3D_PCB1_5_2026-09-15_no_U31-U45_U48_headers.step'
OUT = HERE / 'cache'
OUT.mkdir(exist_ok=True)
R = np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], float)
T = np.array([164.639, -1.6384, -4.146 + 2.75])

reader = STEPCAFControl_Reader(); reader.SetNameMode(True)
assert reader.ReadFile(str(SRC)) == IFSelect_RetDone
doc = TDocStd_Document(TCollection_ExtendedString('pcb')); assert reader.Transfer(doc)
tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
roots = Sequence_TDF_Label(); tool.GetFreeShapes(roots)
parts = Sequence_TDF_Label(); tool.GetComponents_s(roots.Value(1), parts, False)
data, index = {}, []
for i in range(1, parts.Length() + 1):
    label = parts.Value(i); ref = TDF_Label(); tool.GetReferredShape_s(label, ref)
    attr = TDataStd_Name(); ref.FindAttribute(TDataStd_Name.GetID_s(), attr); name = attr.Get().ToExtString()
    shape = tool.GetShape_s(label)
    BRepMesh_IncrementalMesh(shape, 0.08, False, 0.25, True)
    ex = TopExp_Explorer(shape, TopAbs_FACE); verts, faces = [], []
    while ex.More():
        face = TopoDS.Face_s(ex.Current()) if hasattr(TopoDS, 'Face_s') else TopoDS.Face(ex.Current())
        loc = TopLoc_Location(); tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            base = len(verts); trsf = loc.Transformation()
            for j in range(1, tri.NbNodes() + 1):
                p = tri.Node(j).Transformed(trsf); verts.append((p.X(), p.Y(), p.Z()))
            for j in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(j).Get(); ids = [base + a - 1, base + b - 1, base + c - 1]
                if face.Orientation() == TopAbs_REVERSED: ids = ids[::-1]
                faces.append(ids)
        ex.Next()
    if not verts:
        continue
    v = np.asarray(verts) @ R.T + T; f = np.asarray(faces, np.int32)
    k = len(index)
    data[f'p{k}_v'] = v.astype(np.float32); data[f'p{k}_f'] = f
    index.append(dict(key=f'p{k}', name=name, short=name.split('~')[0],
                      lo=np.round(v.min(0), 3).tolist(), hi=np.round(v.max(0), 3).tolist()))
np.savez_compressed(OUT / 'pcb_parts.npz', **data)
(OUT / 'pcb_parts.json').write_text(json.dumps(index, indent=1), encoding='utf8')
print('parts', len(index))
