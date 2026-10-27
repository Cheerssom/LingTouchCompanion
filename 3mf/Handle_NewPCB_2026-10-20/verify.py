"""Verify the three shells and three tenons: hardware fit, tenon capture,
cover removal from the tray, print poses, overhangs, and exact 3MF meshes."""
import json,itertools,zipfile,hashlib,math,xml.etree.ElementTree as ET
import numpy as np
import build as B
H=B.H;M=B.M;md=B.md
parts,refs,visual,dims=B.build()
SHELLS=['Tray','Front_cover','Rear_cover']
r={'parts':{},'collisions_mm3':[],'board_edges':{},'mounts':[],'tenons':{},'archives':{}}
assert list(parts)==SHELLS+B.TENONS,list(parts)
for n,m in parts.items():
    v,f=B.arrays(m);t=B.trimesh.Trimesh(v,f,process=False)
    assert t.is_watertight and t.is_winding_consistent and t.volume>0 and len(m.decompose())==1,n
    r['parts'][n]={'connected_watertight':True,'volume_mm3':m.volume()}
for pn,p in parts.items():
    for rn,ref in refs.items():
        vol=(p^ref).volume()
        if vol>.005:r['collisions_mm3'].append([pn,rn,vol])
for (an,a),(bn,b) in itertools.combinations(parts.items(),2):
    vol=(a^b).volume()
    if vol>.005:r['collisions_mm3'].append([an,bn,vol])
assert not r['collisions_mm3'],r['collisions_mm3']
tray=parts['Tray'];front=parts['Front_cover'];rear=parts['Rear_cover'];covers=front+rear
board=refs['Board']

# PCB: both long edges on the tray ledges, both holes on tray pads with
# pins through them into cover sockets; cover pads stop the board lifting.
bb=board.bounding_box();edge=max(abs(bb[1]),abs(bb[4]))
for sign in [-1,1]:
    ya,yb=sorted([sign*B.LEDGE_INNER_Y,sign*(edge-.02)])
    footprint=board.translate((0,0,-.1))^B.box([.06,ya,-.1],[B.BOARD_L-.06,yb,0])
    missing=(footprint-tray).volume();assert missing<1e-5
    r['board_edges'][str(sign)]={'supported_width_mm':edge-B.LEDGE_INNER_Y,'missing_mm3':missing}
for x,y in B.HOLES:
    cover,cname=(front,'Front_cover') if x<B.SEAM else (rear,'Rear_cover')
    pad=B.cylinder(x,y,-.1,B.SEAT_RADIUS,.1);assert (pad-tray).volume()<1e-5
    # Tray pin: solid through the whole hole and 1.8 mm above the board,
    # inside the cover socket with clearance all round and at the tip.
    top=B.PCB_TOP+B.PIN_ABOVE_BOARD
    pin=B.cylinder(x,y,0,B.PIN_RADIUS-.001,top-.001)
    assert (pin-tray).volume()<1e-5 and (tray^board).volume()<1e-5 and (cover^board).volume()<1e-5
    assert (tray^cover).volume()<1e-5
    socket=B.cylinder(x,y,B.PCB_TOP+B.BOARD_TOP_PLAY+.001,B.SOCKET_RADIUS-.001,B.SOCKET_DEPTH-.002)
    assert (socket^cover).volume()<1e-5
    engaged=top-(B.PCB_TOP+B.BOARD_TOP_PLAY)
    # Board cannot slide sideways off the pin, nor lift past the cover pad.
    slid=(board.translate((.2,0,0))^tray^B.cylinder(x,y,0,1,B.PCB_TOP)).volume();assert slid>.001
    lifted=(cover^board.translate((0,0,B.BOARD_TOP_PLAY+.1))^B.cylinder(x,y,0,B.BOSS_RADIUS,4)).volume();assert lifted>.001
    # Cover offset 0.3 mm sideways hits the pin: the pins also align cover and tray.
    aligned=(cover.translate((.3,0,0))^tray^B.cylinder(x,y,0,1,8)).volume();assert aligned>.001
    r['mounts'].append({'xy_mm':[x,y],'cover':cname,'tray_pad_diameter_mm':2*B.SEAT_RADIUS,'cover_pad_diameter_mm':2*B.BOSS_RADIUS,
        'pin_diameter_mm':2*B.PIN_RADIUS,'pin_length_from_board_bottom_mm':top,'pin_above_board_mm':B.PIN_ABOVE_BOARD,
        'hole_diameter_mm':2*B.HOLE_RADIUS,'pin_in_hole_diametral_gap_mm':2*(B.HOLE_RADIUS-B.PIN_RADIUS),
        'socket_diameter_mm':2*B.SOCKET_RADIUS,'socket_depth_mm':B.SOCKET_DEPTH,'pin_in_socket_mm':engaged,
        'pin_tip_clearance_mm':B.SOCKET_DEPTH-engaged,'top_play_mm':B.BOARD_TOP_PLAY,
        'board_slide_blocked_mm3':slid,'lift_stop_contact_mm3':lifted,'cover_shift_blocked_mm3':aligned})

# Tenons: slide in straight along Y with clearance on every face, touching
# nothing anywhere along the way; each one still blocks its two shells parting.
mates={'Front_tenon':('Tray','Front_cover'),'Rear_tenon':('Tray','Rear_cover'),'Middle_tenon':('Front_cover','Rear_cover')}
for n in B.TENONS:
    pin=parts[n];sp=B.pin_spec(n);a,b=(parts[k] for k in mates[n]);pair=a+b
    for delta in np.linspace(-2*sp['half']-3,2*sp['half']+3,15):
        overlap=(pin.translate((0,float(delta),0))^pair).volume()
        assert overlap<1e-5,(n,'insertion path obstructed',delta,overlap)
    # Clearance all round: shifting the tenon by just under the clearance
    # along X or Z still touches nothing.
    c=B.TENON_CLEAR*.95
    for d in [(c,0,0),(-c,0,0),(0,0,c),(0,0,-c)]:
        assert (pin.translate(d)^pair).volume()<1e-5,(n,'clearance below nominal',d)
    if n=='Middle_tenon':
        # Covers pulled apart along X, or the front cover's seam end lifted.
        blocks={'front_cover_minus_x_2mm':(pin^front.translate((-2,0,0))).volume(),
                'rear_cover_plus_x_2mm':(pin^rear.translate((2,0,0))).volume(),
                'front_cover_lift_2mm':(pin^front.translate((0,0,2))).volume(),
                'rear_cover_lift_2mm':(pin^rear.translate((0,0,2))).volume()}
        retention='45-degree chevron; covers held down by the tray tenons'
    else:
        blocks={'cover_lift_2mm':(pin^b.translate((0,0,2))).volume(),'tray_drop_2mm':(pin^a.translate((0,0,-2))).volume()}
        retention='hourglass across Z=0'
    assert min(blocks.values())>.01,(n,'fails capture',blocks)
    r['tenons'][n]={**sp,'joins':mates[n],'capture_interference_mm3':blocks,'retention':retention+'; loose slide fit, nothing holds it along Y; no printed fit measurement'}

# Covers come off the tray as one piece once the front and rear tenons are
# out; the middle tenon stays in. The two covers are not meant to part.
lid=covers+parts['Middle_tenon']
for dz in [.3,1,5,30]:
    assert (lid.translate((0,0,dz))^tray).volume()<.005,('cover removal',dz)
    for n,m in refs.items():
        if n=='FPC_antenna':continue  # adhered inside the front cover
        assert (lid.translate((0,0,dz))^m).volume()<.005,(n,'cover removal',dz)
r['covers_lift_off_tray_with_middle_tenon']=True
r['cover_seam']={'x_mm':B.SEAM,'slope_x_mm':[B.SLOPE_START,B.SEAM],'esp_front_x_mm':float(refs['ESP_PCB'].bounding_box()[0]),
                 'separation_required':False}
assert B.SEAM<refs['ESP_PCB'].bounding_box()[0]

# Open tail: the PB can pass the tail opening; only the rear tenon stops it.
for dx in [1,3,8,20]:
    assert ((tray+covers)^refs['PB503'].translate((dx,0,0))).volume()<.005,('tail blocked',dx)
end_probe=B.box([B.TAIL-.1,-B.PB_WIDTH/2,B.PB_Z-B.PB_THICKNESS/2],[B.TAIL+.1,B.PB_WIDTH/2,B.PB_Z+B.PB_THICKNESS/2])
assert ((tray+covers)^end_probe).volume()<.005,'end wall remains'
stop=(parts['Rear_tenon']^refs['PB503'].translate((3,0,0))).volume();assert stop>1,'rear tenon does not stop PB'
r['open_tail']={'PB_rear_x_mm':B.PB_X+B.PB_LENGTH,'rear_tenon_front_x_mm':B.pin_spec('Rear_tenon')['x']-B.pin_spec('Rear_tenon')['width']/2,'PB_stop_at_3mm_travel_mm3':stop}

# Outer form: symmetric, one flat top on each cover, one flat tray floor,
# 45-degree slope ending at the seam.
outer=B.tube_envelope();mirror=outer.mirror((0,1,0))
mirror_delta=((outer-mirror)+(mirror-outer)).volume();assert mirror_delta<.001
rows=B.envelope_stations()
assert all(abs(b-B.GRIP_BOTTOM)<1e-9 for x,w,b,*_ in rows)
assert all(abs(t-B.GRIP_TOP)<1e-9 for x,w,b,t,*_ in rows if x>=B.SEAM)
assert all(abs(t-B.FACE)<1e-9 for x,w,b,t,*_ in rows if 0<=x<=B.SLOPE_START)
slope=[(x,t) for x,w,b,t,*_ in rows if B.SLOPE_START<=x<=B.SEAM]
assert all(abs((t1-t0)/(x1-x0)+1)<1e-9 for (x0,t0),(x1,t1) in zip(slope,slope[1:]))
assert abs(front.bounding_box()[5]-B.FACE)<1e-6 and abs(rear.bounding_box()[5]-B.GRIP_TOP)<1e-6 and abs(tray.bounding_box()[2]-B.GRIP_BOTTOM)<1e-6
r['outer']={'mirror_difference_mm3':mirror_delta,'front_cover_top_z':B.FACE,'rear_cover_top_z':B.GRIP_TOP,'tray_floor_z':B.GRIP_BOTTOM,'slope_deg':45.0,'body_length_mm':dims['body_length']}
assert np.allclose(dims['grip_section'],[38.266,32.054]) and dims['body_length']<=272.89+1e-6
assert B.PB_Y==0 and abs(B.PB_Z-5.527)<1e-6 and B.CANE_BORE_DIAMETER==25 and B.CANE_INSERTION==28
gauge=B.cx(B.FRONT+.02,B.FRONT+B.CANE_INSERTION-.02,0,B.AXIS,B.CANE_BORE_DIAMETER/2-.01)
assert ((tray+front)^gauge).volume()<.00001
wall=B.cx(B.FRONT+.02,B.FRONT+B.CANE_INSERTION-.02,0,B.AXIS,B.CANE_BORE_DIAMETER/2+.3)-B.cx(B.FRONT,B.FRONT+B.CANE_INSERTION,0,B.AXIS,B.CANE_BORE_DIAMETER/2+.01)
wall-=B.box([-25.1,-5.1,B.FPC_TOP-5.1],[0,5.1,B.FPC_TOP+.1])  # antenna recess opening
assert (wall-(tray+front)).volume()<.01,'cane bore not a full circle'
r['cane_bore']='full 25 mm circle in tray and front cover, 28 mm deep'

# Top: three row windows with two ribs, separate U48 window, round SW1 hole.
contours=front.slice(B.FACE-.15).to_polygons()
areas=[float(np.sum(a[:,0]*np.roll(a[:,1],-1)-a[:,1]*np.roll(a[:,0],-1))/2) for a in contours]
assert len([a for a in areas if a<0])==5,('top openings',areas)
r['top_face_bounded_openings']=5;r['windows']=dims['windows']
for opening in dims['windows']:
    a=np.array(opening['a']);b=np.array(opening['b'])
    assert (B.box([*a,B.FACE-.5],[*b,B.FACE+.1])^front).volume()<1e-5
ribs=[]
for first,second in zip(dims['windows'][:2],dims['windows'][1:3]):
    ya=first['b'][1];yb=second['a'][1]
    assert (B.box([first['a'][0]+.01,ya+.001,B.FACE-.5],[first['b'][0]-.01,yb-.001,B.FACE-.1])-front).volume()<1e-5,'row rib missing'
    ribs.append(yb-ya)
r['row_rib_widths_mm']=ribs
for name in ['U31','U32','U33','U34','U35','U36','U37','U38','U39','U48']:
    assert abs(refs[name].bounding_box()[5]-B.FACE)<1e-5
r['fixed_module_tops_flush']=True
old=json.loads((M/'hardware_reference_hashes.json').read_text())
current={n:hashlib.sha256(b''.join(a.tobytes() for a in B.arrays(m))).hexdigest() for n,m in refs.items()}
assert current==old,'Hardware changed';r['hardware_references_unchanged']=True

# Print poses and overhangs. Accepted by Hsinlung: tray bottom-edge ring,
# cover top-edge ring, underside of the lower cane-mouth top. Anything else
# flatter than 30 degrees, or any layer starting in mid-air, fails.
pose=json.loads((M/'verification.json').read_text())['print_transforms']
for n,R in B.PRINT_ROTATION.items():assert np.allclose(pose[n]['rotation'],R),n
LH=.2;EXT=LH/math.tan(math.radians(30))
def accepted(n,a,h,edge=True):
    # edge=False for whole-layer regions: an edge ring decomposes as one loop
    # centred on the axis; the per-face test still checks the edge band.
    w,bot,top,rb,rt=B.section_params(float(a[0]))
    if n=='Tray':return h<=2.0 and (not edge or abs(a[1])>=w/2-rb-.5)
    if n=='Front_cover' and a[0]<.5:return True
    return n in ['Front_cover','Rear_cover'] and h<=1.0 and (not edge or abs(a[1])>=w/2-rt-.5)
r['overhangs']={}
for n,m in parts.items():
    R=np.array(pose[n]['rotation']);t=np.array(pose[n]['translation'])
    pm=m.transform(np.hstack([R,t[:,None]]).tolist())
    assert abs(pm.bounding_box()[2])<1e-6,(n,'not on bed')
    v,f=B.arrays(pm);tm=B.trimesh.Trimesh(v,f,process=False)
    down=(tm.face_normals[:,2]<-math.cos(math.radians(30)))&(v[f][:,:,2].max(1)>.02)
    faces={'accepted':0.,'other':0.}
    for i in np.where(down)[0]:
        c=v[f[i]].mean(0);faces['accepted' if accepted(n,(c-t)@R,c[2]) else 'other']+=tm.area_faces[i]
    layers={'accepted':0.,'other':0.};prev=None
    for z in np.arange(LH/2,pm.bounding_box()[5],LH):
        cur=pm.slice(float(z))
        if prev is not None:
            for g in (cur-prev.offset(EXT,md.JoinType.Round)).decompose():
                if g.area()<.02:continue
                b=g.bounds();c=np.array([(b[0]+b[2])/2,(b[1]+b[3])/2,z])
                layers['accepted' if accepted(n,(c-t)@R,z,False) else 'other']+=g.area()
        prev=cur
    assert faces['other']<.01 and layers['other']<.01,(n,faces,layers)
    r['overhangs'][n]={'downward_faces_under_30deg_mm2':faces,'layer_overhang_mm2':layers}
r['print_poses']={'Tray':'floor down','Front_cover':'top face down','Rear_cover':'top face down',
                  'Front_tenon':'broad flat end down','Rear_tenon':'broad flat end down','Middle_tenon':'standing on its end'}

ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
for filename in ['Handle_Print_H2C.3mf','Handle_Assembly.3mf']:
    with zipfile.ZipFile(H/filename) as z:
        if 'Print' in filename:
            c=ET.fromstring(z.read('Metadata/model_settings.config'))
            assert len(c.findall('object/part'))==6 and all(p.get('subtype')=='normal_part' for p in c.findall('object/part'))
    scene=B.trimesh.load(H/filename,force='scene',process=False)
    names={p.get('id'):next(e.get('value') for e in p.findall('metadata') if e.get('key')=='name') for p in c.findall('object/part')} if 'Print' in filename else {}
    obs={}
    for node in scene.graph.nodes_geometry:
        matrix,geometry=scene.graph[node]
        mesh=scene.geometry[geometry].copy();mesh.apply_transform(matrix)
        obs[names.get(str(geometry),str(geometry))]=mesh
    for n,m in parts.items():
        mesh=obs[n];v=mesh.vertices.copy();f=mesh.faces
        t=B.trimesh.Trimesh(v,f,process=False);assert t.is_watertight and t.is_winding_consistent
        if 'Print' in filename:
            assert abs(v[:,2].min())<1e-6
            v=(v-np.array(pose[n]['translation']))@np.array(pose[n]['rotation'])
        ev,ef=B.arrays(m)
        # Native Bambu export recentres meshes and rounds coordinates to float32.
        assert np.array_equal(f,ef) and np.allclose(v,ev,atol=.00005,rtol=0),(n,filename)
    r['archives'][filename]='mesh triangles and pose readback passed; native coordinate tolerance 0.00005 mm'
sr=json.loads((M/'slice_verification.json').read_text());assert sr['sha256']['output_sha256']==hashlib.sha256((H/'Handle_Print_H2C.3mf').read_bytes()).hexdigest()
assert sr['support_by_category_g'].get('NOT accepted',0)<.001,sr['support_by_category_g']
r['native_slice']={'support_g':sr['support_g'],'support_by_category_g':sr['support_by_category_g'],'system_process_differences':sr['process_default_differences']}
(M/'fit_verification.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r,indent=2))
