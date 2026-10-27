"""Read retained sources; write measured CAD evidence only inside this folder."""
from pathlib import Path
import json, sys, zipfile, hashlib
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
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
from OCP.TopAbs import TopAbs_FACE,TopAbs_REVERSED
from OCP.TopoDS import TopoDS
from OCP.TopLoc import TopLoc_Location
from OCP.IFSelect import IFSelect_RetDone
OUT=HERE/'models';OUT.mkdir(exist_ok=True)
SRC=ROOT/'.pcba-workflow/pcb1_2-review-20261018/PCB1_2_review.step'
reader=STEPCAFControl_Reader();reader.SetNameMode(True)
assert reader.ReadFile(str(SRC))==IFSelect_RetDone
doc=TDocStd_Document(TCollection_ExtendedString('pcb'));assert reader.Transfer(doc)
tool=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
roots=Sequence_TDF_Label();tool.GetFreeShapes(roots)
parts=Sequence_TDF_Label();tool.GetComponents_s(roots.Value(1),parts,False)
data,index={},[]
for i in range(1,parts.Length()+1):
    label=parts.Value(i);ref=TDF_Label();tool.GetReferredShape_s(label,ref)
    attr=TDataStd_Name();ref.FindAttribute(TDataStd_Name.GetID_s(),attr);name=attr.Get().ToExtString()
    shape=tool.GetShape_s(label);BRepMesh_IncrementalMesh(shape,.08,False,.25,True)
    ex=TopExp_Explorer(shape,TopAbs_FACE);verts,faces=[],[]
    while ex.More():
        face=TopoDS.Face_s(ex.Current()) if hasattr(TopoDS,'Face_s') else TopoDS.Face(ex.Current())
        loc=TopLoc_Location();tri=BRep_Tool.Triangulation_s(face,loc)
        if tri is not None:
            base=len(verts);trsf=loc.Transformation()
            for j in range(1,tri.NbNodes()+1):
                p=tri.Node(j).Transformed(trsf);verts.append((p.X(),p.Y(),p.Z()))
            for j in range(1,tri.NbTriangles()+1):
                a,b,c=tri.Triangle(j).Get();ids=[base+a-1,base+b-1,base+c-1]
                if face.Orientation()==TopAbs_REVERSED:ids=ids[::-1]
                faces.append(ids)
        ex.Next()
    if not verts:continue
    v=np.array(verts);f=np.array(faces,np.int32);k=f'p{len(index)}'
    data[k+'_v']=v.astype(np.float32);data[k+'_f']=f
    index.append(dict(key=k,name=name,short=name.split('~')[0],lo=v.min(0).round(3).tolist(),hi=v.max(0).round(3).tolist()))
np.savez_compressed(OUT/'pcb_parts.npz',**data)
(OUT/'pcb_parts.json').write_text(json.dumps(index,indent=1),encoding='utf8')
rows=json.loads((HERE/'models/pcb_parts.json').read_text())
for r in rows:
    print(r['short'],r['lo'],r['hi'])
# Extract native footprint pad positions alongside the component placement.
with zipfile.ZipFile(ROOT/'.pcba-workflow/pcb1_2-review-20261018/PCB1_2_snapshot.epro2') as z:
    s=z.read(next(n for n in z.namelist() if n.endswith('.epru'))).decode('utf8')
docs={}
for line in s.splitlines():
    if '||' not in line: continue
    try:
        h,d=line.split('||',1); h=json.loads(h); d=json.loads(d.rstrip('|'))
    except ValueError: continue
    if h['type']=='DOCHEAD': current=d['uuid']; docs[current]=[]
    docs[current].append((h,d))
board=docs['b5f51a2d415c68f2']
attrs={d['parentId']:d['value'] for h,d in board if h['type']=='ATTR' and d.get('key')=='Designator'}
components={attrs.get(h['id'],h['id']):d for h,d in board if h['type']=='COMPONENT'}
out={'components':components,'module_pads':[d for h,d in docs['69fcb5cc3cb5d8a8'] if h['type']=='PAD']}
(HERE/'models/native_positions.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print('NATIVE',json.dumps({r:components.get(r) for r in ['U31','U32','U33','U34','U35','U36','U37','U38','U39','U48','SW1','SW2','J1','U46','U47']},indent=1))
