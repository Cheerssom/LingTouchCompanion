"""Parametric PCB1_2 / PB503 coaxial handle: lower tray, front cover (cane
mouth + module area + 45-degree slope), rear cover (grip + tail), and three
separately printed tenons. Units mm; X cane-to-tail, Y board width, Z PCB
normal. Run with ../.runtime/structural-runtime/Scripts/python.exe -B.
Only writes to this directory. build.py also validates and exports both 3MFs.
"""
from pathlib import Path
import json, math, itertools, zipfile, hashlib, sys
import xml.etree.ElementTree as ET
import numpy as np
import manifold3d as md
import trimesh

# ---- FDM assembly clearances and fixed hardware dimensions, mm. ----
MODULE_SEATED_HEIGHT = 24.30
SOCKET_HEIGHT, MODULE_BASE_HEIGHT = 4.30, 3.40
ESP_LENGTH, ESP_WIDTH = 57.15, 27.94
ESP_FEMALE_HEIGHT, ESP_MALE_SPACER, ESP_PCB_THICKNESS = 8.50, 2.50, 1.60
ESP_TOP_HEIGHT = 4.0
PB_LENGTH, PB_WIDTH, PB_THICKNESS = 79.0, 38.5, 26.5
CONNECTOR_GAP, TAIL_LENGTH = 13.5, 8.5
FRONT_WALL_EXTENSION = 2.0
BOARD_SIDE_CLEAR, WINDOW_CLEAR, PB_CLEAR = .35, .35, .35
WALL, CANE_BORE_DIAMETER, CANE_INSERTION = 2.40, 25.0, 28.0
SW1_ACCESS_RADIUS = 2.5
FPC_SIZE = (20., 8., .15)
LEDGE_INNER_Y, LEDGE_DEPTH = 15.80, 1.30
SEAT_RADIUS, BOSS_RADIUS = 1.10, 1.10
BOARD_TOP_PLAY = .20
# PCB hole locating: 1.0 mm tray pin through the 1.2 mm hole, 1.8 mm above
# the board top, into a 1.3 mm x 1.8 mm deep socket in the cover post.
PIN_RADIUS, PIN_ABOVE_BOARD = .50, 1.80
SOCKET_RADIUS, SOCKET_DEPTH = .65, 1.80
SOLDER_RADIUS, TAIL_BELOW_PCB = .50, 1.80
SPLINE_HEIGHT = 7.0
TENON_CLEAR = .20  # per face, whole length; tenons slide in, nothing is tight
FRONT_CAVITY_START = -.35

H=Path(__file__).resolve().parent; ROOT=H.parents[1]; M=H/'models'; M.mkdir(exist_ok=True)
PCB_TOP=2.204; BOARD_L=135.89; BOARD_W=32.766
T=np.array([128.397,43.053,0.0])
FACE=PCB_TOP+MODULE_SEATED_HEIGHT
PB_X=BOARD_L+CONNECTOR_GAP
PB_Y=0.0
HARDWARE_CLEAR = 0.35
GRIP_BOTTOM = -7.75-HARDWARE_CLEAR-WALL  # C76 unchanged
GRIP_TOP = PCB_TOP+ESP_FEMALE_HEIGHT+ESP_MALE_SPACER+ESP_PCB_THICKNESS+ESP_TOP_HEIGHT+HARDWARE_CLEAR+WALL
AXIS=(GRIP_TOP+GRIP_BOTTOM)/2
PB_Z=AXIS
# The PB section needs 21.527 / -10.473; the 0.027 mm difference to the grip is
# taken as extra PB clearance so each cover top and the tray floor is one plane.
assert PB_Z+PB_THICKNESS/2+PB_CLEAR+WALL<=GRIP_TOP and PB_Z-PB_THICKNESS/2-PB_CLEAR-WALL>=GRIP_BOTTOM
BANK_TOP=GRIP_TOP
BOTTOM=GRIP_BOTTOM
FPC_TOP=AXIS+18-WALL
# 45-degree slope from the module face down to the grip, entirely in the front
# cover; the cover-to-cover seam is the slope foot, ahead of the ESP.
U48_WINDOW_END=54.166  # asserted against window_specs() in build()
SLOPE_START=U48_WINDOW_END+WALL
SEAM=SLOPE_START+(FACE-GRIP_TOP)
# Middle tenon joining the two covers above the PCB (local parts <= Z 4.105):
# a chevron, both 45-degree arms dipping to the seam. In each cover printed
# top down, the slot ceiling then rises from the far end wall to the seam.
MID_HALF=4.0; MID_LOW=5.0; MID_THICK=5.0; MID_TIP=.4
ARRAY_W=BOARD_W+2*(.85+WALL)
# Existing manufactured holes, read directly from recorded EDA evidence.
EVIDENCE=ROOT/'.pcba-workflow/pcb1_2-recheck-20261018/live-check-evidence.json'
_evidence=json.loads(EVIDENCE.read_text(encoding='utf8'))
HOLE_IDS=['8a08118428949267','845a3a28dd9fe12d']
HOLES=[]
for _id in HOLE_IDS:
    _row=next(c for c in _evidence['physical_changes'] if c['id']==_id)
    _path=_row['new']['path'][0]
    HOLES.append((_path[1]*.0254+T[0],_path[2]*.0254+T[1]))
HOLE_RADIUS=.6 # Hsinlung confirmed 10/21
TAIL=PB_X+PB_LENGTH+TAIL_LENGTH
FRONT=-34.0-FRONT_WALL_EXTENSION
GRIP_W=BOARD_W+2*(BOARD_SIDE_CLEAR+WALL)
BAT_W=2*max(abs(PB_Y-PB_WIDTH/2),abs(PB_Y+PB_WIDTH/2))+2*(PB_CLEAR+WALL)

def box(a,b):
    a=np.array(a,float); b=np.array(b,float)
    return md.Manifold.cube(b-a).translate(a)
def cylinder(x,y,z,r,h,n=64):
    return md.Manifold.cylinder(h,r,circular_segments=n).translate((x,y,z))
def cx(x0,x1,y,z,r,n=128):
    return md.Manifold.cylinder(x1-x0,r,circular_segments=n).rotate((0,90,0)).translate((x0,y,z))
# Fixed maximum section envelope; the corner lands are cut inward.
ARC_STEPS=64
ARRAY_RADII=(13.47,3.21) # bottom, top; flat array face includes 0.80 mm window land
GRIP_RADII=(10.87,5.33)
BANK_RADII=(3.02,3.02)

def rounded_section(w,h,z0,rb,rt=None):
    rt=rb if rt is None else rt
    assert rb+rt<h and 2*max(rb,rt)<w
    y=w/2;top=z0+h;points=[]
    for cy,cz,r,start in [(y-rb,z0+rb,rb,-90),(y-rt,top-rt,rt,0),
                           (-y+rt,top-rt,rt,90),(-y+rb,z0+rb,rb,180)]:
        for angle in np.radians(np.linspace(start,start+90,ARC_STEPS+1)):
            points.append((cy+r*math.cos(angle),cz+r*math.sin(angle)))
    return points

def loft(stations):
    v=[]
    for row in stations:
        x,w,bot,top,rb,*extra=row;rt=extra[0] if extra else rb
        v.extend((x,y,z) for y,z in rounded_section(w,top-bot,bot,rb,rt))
    f=[];n=4*(ARC_STEPS+1)
    for k in range(len(stations)-1):
        for j in range(n):
            a=k*n+j;b=k*n+(j+1)%n;c=(k+1)*n+(j+1)%n;d=(k+1)*n+j
            f.extend([(a,b,c),(a,c,d)])
    for j in range(1,n-1):
        f.append((0,j+1,j));f.append(((len(stations)-1)*n,(len(stations)-1)*n+j,(len(stations)-1)*n+j+1))
    tm=trimesh.Trimesh(v,f,process=True);tm.fix_normals()
    solid=md.Manifold(md.Mesh(np.array(tm.vertices,np.float32),np.array(tm.faces,np.uint32)))
    assert solid.status()==md.Error.NoError
    return solid

CANE=(36,GRIP_BOTTOM,AXIS+18,10,12)
ARRAY=(ARRAY_W,GRIP_BOTTOM,FACE,*ARRAY_RADII)
GRIP=(GRIP_W,GRIP_BOTTOM,GRIP_TOP,*GRIP_RADII)
BANK=(BAT_W,BOTTOM,BANK_TOP,*BANK_RADII)
INNER_CREASE=WALL*(math.sqrt(2)-1)  # inner slope creases sit this far ahead

def blend(a,b,u):
    q=u*u*(3-2*u); return [p+(r-p)*q for p,r in zip(a,b)]

def section_params(x,inner=False):
    """Outer (or WALL-offset inner) section at X: width, bottom, top, rb, rt."""
    if x<=-7: w,bot,top,rb,rt=CANE
    elif x<0: w,bot,top,rb,rt=blend(CANE,ARRAY,(x+7)/7)
    elif x<=SLOPE_START: w,bot,top,rb,rt=ARRAY
    elif x<SEAM:
        w,bot,_,rb,rt=blend(ARRAY,GRIP,(x-SLOPE_START)/(SEAM-SLOPE_START))
        top=FACE-(x-SLOPE_START)  # exact 45 degrees
    elif x<=122: w,bot,top,rb,rt=GRIP
    elif x<PB_X: w,bot,top,rb,rt=blend(GRIP,BANK,(x-122)/(PB_X-122))
    else: w,bot,top,rb,rt=BANK
    if not inner: return w,bot,top,rb,rt
    d=WALL; itop=top-d
    if SLOPE_START-INNER_CREASE-1e-9<=x<=SEAM:
        # Normal offset of the 45-degree roof keeps the full wall thickness.
        itop=min(FACE-d,max(GRIP_TOP-d,FACE-(x-SLOPE_START)-d*math.sqrt(2)))
    return w-2*d,bot+d,itop,rb-d,rt-d

def envelope_xs():
    xs=[FRONT,*np.linspace(-7,0,25),SLOPE_START-INNER_CREASE,*np.linspace(SLOPE_START,SEAM,25),
        SEAM-INNER_CREASE,*np.linspace(122,PB_X,25),TAIL]
    return sorted(set(round(float(x),9) for x in xs))

def envelope_stations(inner=False):
    return [(x,*section_params(x,inner)) for x in envelope_xs()]

def tube_envelope(inner=False):
    rows=envelope_stations(inner)
    if inner:  # open tail: the cavity runs 2 mm past the end
        rows[0]=(rows[0][0]+WALL,*rows[0][1:]);rows[-1]=(rows[-1][0]+2.0,*rows[-1][1:])
    return loft(rows)

def section_dimensions(x):
    w,bot,top,rb,rt=section_params(x)
    yz=np.array(rounded_section(w,top-bot,bot,rb,rt))
    perimeter=float(np.linalg.norm(yz-np.roll(yz,1,axis=0),axis=1).sum())
    return dict(x=x,width=w,height=top-bot,perimeter=perimeter,bottom=bot,top=top,bottom_outer_radius=rb,top_outer_radius=rt)

def arrays(m):
    mesh=m.to_mesh64(); return np.array(mesh.vert_properties[:,:3]),np.array(mesh.tri_verts)
def transform_body(bounds,d):
    x0,y0,x1,y1=bounds; a=math.radians(d['angle']); r=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
    p=np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])@r.T+np.array([d['x'],d['y']])*.0254+T[:2]
    return p.min(0),p.max(0)

def native_references():
    if not (M/'native_positions.json').exists():
        import subprocess
        subprocess.run([sys.executable,'-B',str(H/'measure_sources.py')],check=True,stdout=subprocess.DEVNULL)
    native=json.loads((M/'native_positions.json').read_text()); comps=native['components']
    refs={}; visual={}; raw=np.load(M/'pcb_parts.npz'); idx=json.loads((M/'pcb_parts.json').read_text())
    # Keep exported component envelopes; ESP headers use specified 8.5 mm bodies.
    for p in idx:
        name=p['short']
        if name in ['J_ESP_R','J_ESP_L']: continue
        v=raw[p['key']+'_v'].astype(float)+T; f=raw[p['key']+'_f']
        # Reconcile the two moved components using the actual recorded centre and rotation.
        if name in ['C33','D3']:
            nc=np.array([-34.036,-43.180]) if name=='C33' else np.array([5.715,-29.845])
            c=(v.min(0)+v.max(0))/2
            rot=np.array([[0,-1],[1,0]]) if name=='C33' else np.array([[0,1],[-1,0]])
            v[:,:2]=(v[:,:2]-c[:2])@rot+nc+T[:2]
        visual[name]=(v,f)
        if name=='Board':
            # Add only the two already-manufactured holes to the older STEP reference.
            tm=trimesh.Trimesh(v,f,process=True)
            board=md.Manifold(md.Mesh(tm.vertices.astype(np.float32),tm.faces.astype(np.uint32)))
            assert board.status()==md.Error.NoError and board.volume()>9000
            for x,y in HOLES: board-=cylinder(x,y,-1,HOLE_RADIUS,PCB_TOP+2,96)
            refs[name]=board; visual[name]=arrays(board)
        elif name=='SW2':
            # Exact actuator instead of convex-hulling the empty space around it.
            refs[name]=md.Manifold.hull_points(v[v[:,0]<132.0])+box([133.89,3.438,4.704],[135.894,5.438,6.704])
        else: refs[name]=md.Manifold.hull_points(v)
    modbounds=[]
    for name in ['U31','U32','U33','U34','U35','U36','U37','U38','U39','U48']:
        d=comps[name]
        # Centre and keyed-base origin recovered from native pads, never STEP placeholder.
        # Footprint pad average = origin; supplier key-end extends 2.20 beyond pin 7.
        top0,top1=transform_body((-3,-4.1,3,4.1),d)
        base0,base1=transform_body((-3,.30+2.5*1.25+2.2-10.82,3,.30+2.5*1.25+2.2),d)
        m=box([*top0,PCB_TOP+SOCKET_HEIGHT],[*top1,FACE])
        m+=box([*base0,PCB_TOP+SOCKET_HEIGHT],[*base1,PCB_TOP+SOCKET_HEIGHT+MODULE_BASE_HEIGHT])
        refs[name]=m; visual[name]=arrays(m); modbounds.append((name,top0,top1))
        # Two individual socket strips in footprint-local coordinates.
        pads=sorted(native['module_pads'],key=lambda p:int(p['num']))
        for j,row in enumerate([pads[:6],pads[6:]]):
            px=np.mean([p['centerX'] for p in row])*.0254; py=np.mean([p['centerY'] for p in row])*.0254
            a,b=transform_body((px-1.125,py-4.16,px+1.125,py+4.16),d)
            refs[f'{name}_socket{j}']=box([*a,PCB_TOP],[*b,PCB_TOP+4.45]); visual[f'{name}_socket{j}']=arrays(refs[f'{name}_socket{j}'])
    # ESP rows locate its PCB; +/-1.905 end allowance from metric drawing.
    esp_z=PCB_TOP+ESP_FEMALE_HEIGHT+ESP_MALE_SPACER
    ecx=comps['J_ESP_R']['x']*.0254+T[0]
    ey=(comps['J_ESP_R']['y']+comps['J_ESP_L']['y'])/2*.0254+T[1]
    ex0=ecx-ESP_LENGTH/2
    refs['ESP_PCB']=box([ex0,ey-ESP_WIDTH/2,esp_z],[ex0+ESP_LENGTH,ey+ESP_WIDTH/2,esp_z+ESP_PCB_THICKNESS])
    refs['ESP_components']=box([ex0+1,ey-12.0,esp_z+ESP_PCB_THICKNESS],[ex0+ESP_LENGTH+.5,ey+12,esp_z+ESP_PCB_THICKNESS+ESP_TOP_HEIGHT])
    for j,ref in enumerate(['J_ESP_L','J_ESP_R']):
        y=comps[ref]['y']*.0254+T[1]
        refs[f'ESP_socket{j}']=box([ecx-27.94,y-1.25,PCB_TOP],[ecx+27.94,y+1.25,PCB_TOP+ESP_FEMALE_HEIGHT])
        refs[f'ESP_spacer{j}']=box([ecx-27.94,y-1.25,PCB_TOP+ESP_FEMALE_HEIGHT],[ecx+27.94,y+1.25,esp_z])
    for ref in ['J_ESP_L','J_ESP_R']:
        d=comps[ref]; y=d['y']*.0254+T[1]
        # 22 contacts at 2.54 pitch, same row centre as the supplied reference.
        for k in range(22):
            x=ecx+(k-10.5)*2.54
            refs[f'{ref}_tail{k}']=cylinder(x,y,-TAIL_BELOW_PCB,SOLDER_RADIUS,TAIL_BELOW_PCB)
    for name in ['U31','U32','U33','U34','U35','U36','U37','U38','U39','U48']:
        d=comps[name]
        for pad in native['module_pads']:
            px,py=pad['centerX']*.0254,pad['centerY']*.0254
            a,b=transform_body((px,py,px,py),d);x,y=a
            refs[f'{name}_tail{pad["num"]}']=cylinder(x,y,-TAIL_BELOW_PCB,SOLDER_RADIUS,TAIL_BELOW_PCB)
    refs['PB503']=box([PB_X,PB_Y-PB_WIDTH/2,PB_Z-PB_THICKNESS/2],[PB_X+PB_LENGTH,PB_Y+PB_WIDTH/2,PB_Z+PB_THICKNESS/2])
    refs['FPC_antenna']=box([-4-FPC_SIZE[0],-FPC_SIZE[1]/2,FPC_TOP-FPC_SIZE[2]],[-4,FPC_SIZE[1]/2,FPC_TOP])
    for n,m in refs.items():
        if n not in visual: visual[n]=arrays(m)
    return refs,visual,modbounds

def prism_y(x, y0, y1, profile):
    # profile = X offset / Z, CCW in XZ. Orient a native XY extrusion into Y.
    return md.CrossSection([profile]).extrude(y1-y0).rotate((90,0,0)).translate((x,y1,0))

TENONS=['Front_tenon','Rear_tenon','Middle_tenon']

def pin_spec(name):
    """Front/rear: hourglass across the cover/tray split Z=0, removable.
    Middle: 45-degree chevron across the vertical cover seam; with both covers
    held down by the tray, each arm blocks the covers from parting along X."""
    common=dict(clearance_per_face=TENON_CLEAR)
    if name=='Middle_tenon':
        half=section_dimensions(SEAM)['width']/2
        return dict(common,x=SEAM,half=half,width=2*MID_HALF,seam_bottom=MID_LOW,
                    vertical_thickness=MID_THICK,end_top=MID_LOW+MID_HALF+MID_THICK,
                    length=2*half,direction=1)
    front=name=='Front_tenon'
    x=(FRONT+CANE_INSERTION+FRONT_CAVITY_START)/2 if front else PB_X+PB_LENGTH+4.425
    half=section_dimensions(x)['width']/2
    return dict(common,x=x,half=half,width=4.45 if front else 4.95,
                waist=2.85 if front else 3.35,height=SPLINE_HEIGHT,
                length=2*half+2.,direction=1 if front else -1)

def pin_profile(name,channel=True):
    s=pin_spec(name)
    if name=='Middle_tenon':
        a,b,t=MID_HALF,MID_LOW,MID_THICK
        if channel: return [(-a,b+a),(0,b),(a,b+a),(a,b+a+t),(0,b+t),(-a,b+a+t)]
        # The tenon alone blunts its two acute upper tips; the slot keeps them.
        k=MID_TIP
        return [(-a,b+a),(0,b),(a,b+a),(a,b+a+t-k),(a-k,b+a+t-k),(0,b+t),(-a+k,b+a+t-k),(-a,b+a+t-k)]
    w=s['width']/2;n=s['waist']/2;h=s['height']/2
    return [(-w,-h),(w,-h),(n,0),(w,h),(-w,h),(-n,0)]

def make_pin(name):
    s=pin_spec(name);extra=0 if name=='Middle_tenon' else 1
    return prism_y(s['x'],-s['half']-extra,s['half']+extra,pin_profile(name,False))

def pin_cut(name):
    s=pin_spec(name)
    # One straight channel, uniform clearance; miter limit 3 keeps the
    # 45-degree slot corners sharp (no flat bevel).
    section=md.CrossSection([pin_profile(name)]).offset(TENON_CLEAR,md.JoinType.Miter,3.0)
    return section.extrude(2*s['half']+4).rotate((90,0,0)).translate((s['x'],s['half']+2,0))

def window_specs(mb):
    regular=[v for v in mb if v[0]!='U48']
    rows={}
    for n,a,b in regular:rows.setdefault(round(float((a[1]+b[1])/2),4),[]).append((n,a,b))
    groups=[rows[k] for k in sorted(rows)]+[[v for v in mb if v[0]=='U48']]
    return [dict(names=[v[0] for v in group],
                 a=(np.min([v[1] for v in group],axis=0)-WINDOW_CLEAR).tolist(),
                 b=(np.max([v[2] for v in group],axis=0)+WINDOW_CLEAR).tolist()) for group in groups]

def switch_center():
    d=json.loads((M/'native_positions.json').read_text())['components']['SW1']
    return np.array([d['x'],d['y']])*.0254+T[:2]


def build():
    refs,visual,mb=native_references()
    outer=tube_envelope(); cavity=tube_envelope(True)
    cavity=cavity^box([FRONT_CAVITY_START,-100,-100],[TAIL+3,100,100])
    # PB is directly surrounded by the shell, with 0.35 mm nominal assembly clearance.
    # Plain circular 25 mm cane bore, symmetric in both halves.
    cane=cx(FRONT-1,FRONT+CANE_INSERTION,0,AXIS,CANE_BORE_DIAMETER/2)
    shell=outer-cavity-cane
    low=shell^box([-100,-100,-100],[400,100,0])
    up=shell^box([-100,-100,0],[400,100,100])

    # Continuous long-edge ledges at PCB bottom Z=0; the underside runs back
    # into the wall at 45 degrees instead of overhanging flat.
    for sign in [-1,1]:
        y0=LEDGE_INNER_Y
        ledge=md.CrossSection([[(y0,0),(y0,-LEDGE_DEPTH),(y0+4,-LEDGE_DEPTH-4),(y0+4,0)]]).extrude(BOARD_L).rotate((90,0,90))
        low+=(ledge if sign>0 else ledge.mirror((0,1,0)))^outer
    for x,y in HOLES:
        low+=cylinder(x,y,GRIP_BOTTOM+1,SEAT_RADIUS,-GRIP_BOTTOM-1)
        yy=sorted([y,math.copysign(25,y)])
        low+=box([x-.65,yy[0],GRIP_BOTTOM+1],[x+.65,yy[1],0])^outer
        # Tray post carries a pin through the 1.2 mm PCB hole; the cover post
        # stops 0.2 mm above the board and its socket takes the pin tip.
        stop_z=PCB_TOP+BOARD_TOP_PLAY
        low+=cylinder(x,y,-.05,PIN_RADIUS,PCB_TOP+PIN_ABOVE_BOARD+.05)
        up+=cylinder(x,y,stop_z,BOSS_RADIUS,FACE-stop_z)
        up+=box([x-.65,yy[0],stop_z],[x+.65,yy[1],FACE])^outer
        if x<FRONT_CAVITY_START+BOSS_RADIUS+1:
            # Front hole: the posts sit next to the wall behind the cane bore;
            # fill the narrow gap between post, that wall and the side wall.
            ya=sorted([y-math.copysign(BOSS_RADIUS,y),math.copysign(25,y)])
            low+=box([FRONT_CAVITY_START-.01,ya[0],GRIP_BOTTOM+1],[x,ya[1],0])^outer
            up+=box([FRONT_CAVITY_START-.01,ya[0],stop_z],[x,ya[1],FACE])^outer
        if x>100:
            # The slanted web meets the post at its edge, leaving no spike.
            web=md.CrossSection([[(x-8,18.5),(x,abs(y)-BOSS_RADIUS),(x+.65,abs(y)),(x+.65,25),(x-8,25)]]).extrude(FACE-GRIP_BOTTOM).translate((0,0,GRIP_BOTTOM))
            if y<0:web=web.mirror((0,1,0))
            web=web^outer
            low+=web^box([-100,-100,-100],[400,100,0])
            up+=web^box([-100,-100,stop_z],[400,100,100])
    for x,y in HOLES:
        up-=cylinder(x,y,PCB_TOP+BOARD_TOP_PLAY-.01,SOCKET_RADIUS,SOCKET_DEPTH+.01)

    # Two compact side stops retain the PB front end without a full cross-wall.
    for sign in [-1,1]:
        stop=md.CrossSection([[(PB_X-4.,-20.5),(PB_X-PB_CLEAR,-20.5),(PB_X-PB_CLEAR,-18.25)]]).extrude(BANK_TOP-BOTTOM).translate((0,0,BOTTOM))
        if sign>0:stop=stop.mirror((0,1,0))
        stop=stop^outer
        low+=stop^box([-100,-100,-100],[400,100,0])
        up+=stop^box([-100,-100,0],[400,100,100])
    windows=window_specs(mb)
    assert abs(windows[-1]['b'][0]-U48_WINDOW_END)<.001 and windows[-1]['names']==['U48']
    for opening in windows:
        up-=box([*opening['a'],PCB_TOP+SOCKET_HEIGHT],[*opening['b'],FACE+2])
    sx,sy=switch_center()
    up-=cylinder(sx,sy,11.6,SW1_ACCESS_RADIUS,FACE-11.6+2)
    # Antenna recess, no external opening: flat face for the FPC at FPC_TOP,
    # two 45-degree sides meeting below, opening into the cane bore and the cavity.
    up-=md.CrossSection([[(0,FPC_TOP-5),(5,FPC_TOP),(-5,FPC_TOP)]]).extrude(24.8).rotate((90,0,90)).translate((-25,0,0))
    low=low^outer;up=up^outer
    # Front/rear: hourglass across Z=0; the rear one spans the open tail behind
    # the power bank. Middle: across the vertical cover seam, above the PCB.
    for name in TENONS:
        cut=pin_cut(name);low-=cut;up-=cut
    printed={'Tray':low,'Front_cover':up^box([-100,-100,-1],[SEAM,100,100]),
             'Rear_cover':up^box([SEAM,-100,-1],[400,100,100]),
             **{n:make_pin(n) for n in TENONS}}
    printed={n:m.as_original().simplify(.00001) for n,m in printed.items()}
    # Regularize coincident boolean vertices before exchange-file round trips.
    # Removing the resulting zero-area triangles preserves the solid boundary.
    for name,m in printed.items():
        vertices,faces=arrays(m)
        mesh=trimesh.Trimesh(vertices,faces,process=False)
        mesh.merge_vertices(digits_vertex=7)
        mesh.update_faces(mesh.nondegenerate_faces());mesh.update_faces(mesh.unique_faces())
        mesh.remove_unreferenced_vertices()
        assert mesh.is_watertight and mesh.is_winding_consistent,name
        repaired=md.Manifold(md.Mesh64(mesh.vertices,mesh.faces.astype(np.uint64)))
        assert repaired.status()==md.Error.NoError and abs(repaired.volume()-m.volume())<.00001
        printed[name]=repaired

    pin_dimensions={n:pin_spec(n) for n in TENONS}
    dims=dict(axis_z=AXIS,split_z=0,cover_seam_x=SEAM,slope_x=[SLOPE_START,SEAM],
              slope_z=[FACE,GRIP_TOP],body_length=TAIL-FRONT,
              grip_section=[GRIP_W,GRIP_TOP-GRIP_BOTTOM],tail_section=[BAT_W,BANK_TOP-BOTTOM],
              sections={n:section_dimensions(x) for n,x in [('array',34),('grip',90),('power_bank',175)]},
              pb_body_x=[PB_X,PB_X+PB_LENGTH],pins=pin_dimensions,windows=windows,
              switch_center=switch_center().tolist(),switch_diameter=2*SW1_ACCESS_RADIUS)
    return printed,refs,visual,dims


def write3mf(path,objects,transforms=None):
    ns='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'; q='{'+ns+'}'; ET.register_namespace('',ns)
    root=ET.Element(q+'model',unit='millimeter',**{'xml:lang':'en-US'})
    ET.SubElement(root,q+'metadata',name='Title').text='PCB1_2 handle / tray, front cover, rear cover / three tenons'
    resources=ET.SubElement(root,q+'resources'); build=ET.SubElement(root,q+'build')
    config=ET.Element('config')
    if transforms:
        ET.SubElement(root,q+'metadata',name='Application').text='BambuStudio-02.07.01.62'
        ET.SubElement(root,q+'metadata',name='BambuStudio:3mfVersion').text='1'

    colors=['#406B7B','#EBEEE9','#D5A64B','#D5A64B','#219050','#263740','#777777']
    bas=ET.SubElement(resources,q+'basematerials',id='9000')
    for j,c in enumerate(colors): ET.SubElement(bas,q+'base',name=str(j),displaycolor=c+'FF')
    for i,(name,v,f,color) in enumerate(objects,1):
        ob=ET.SubElement(resources,q+'object',id=str(i),type='model',name=name,pid='9000',pindex=str(color))
        me=ET.SubElement(ob,q+'mesh'); vs=ET.SubElement(me,q+'vertices'); fs=ET.SubElement(me,q+'triangles')
        for p in v: ET.SubElement(vs,q+'vertex',x=f'{p[0]:.9f}',y=f'{p[1]:.9f}',z=f'{p[2]:.9f}')
        for t in f: ET.SubElement(fs,q+'triangle',v1=str(t[0]),v2=str(t[1]),v3=str(t[2]))
        if transforms:
            parent_id=100+i
            parent=ET.SubElement(resources,q+'object',id=str(parent_id),type='model',name=name)
            components=ET.SubElement(parent,q+'components')
            ET.SubElement(components,q+'component',objectid=str(i))
            objconfig=ET.SubElement(config,'object',id=str(parent_id))
            ET.SubElement(objconfig,'metadata',key='name',value=name)
            ET.SubElement(objconfig,'metadata',key='extruder',value='1')
            normal=ET.SubElement(objconfig,'part',id=str(i),subtype='normal_part')
            ET.SubElement(normal,'metadata',key='name',value=name)
            ET.SubElement(normal,'metadata',key='matrix',value='1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1')
            ET.SubElement(build,q+'item',objectid=str(parent_id))
        else:ET.SubElement(build,q+'item',objectid=str(i))
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        if transforms:
            z.writestr('Metadata/model_settings.config',ET.tostring(config,encoding='utf-8',xml_declaration=True))
            settings={}
            for profile in ['h2c_machine.json','h2c_process.json','h2c_pla.json']:
                settings.update(json.loads((M/profile).read_text(encoding='utf8')))
            z.writestr('Metadata/project_settings.config',json.dumps(settings))
        z.writestr('3D/3dmodel.model',ET.tostring(root,encoding='utf-8',xml_declaration=True))

# Specified bed faces: tray floor down; both covers top face down (half turn
# about the long axis, no tilt); front/rear tenons as built (broad flat end
# down); middle chevron tenon stands on its end, so its constant profile is
# the bed footprint. Rows: tray / two covers / three tenons.
PRINT_ROTATION={'Tray':np.eye(3),'Front_cover':np.diag([1.,-1,-1]),'Rear_cover':np.diag([1.,-1,-1]),
                'Front_tenon':np.eye(3),'Rear_tenon':np.eye(3),'Middle_tenon':np.array([[1.,0,0],[0,0,-1],[0,1,0]])}
PRINT_ROWS=[['Tray'],['Front_cover','Rear_cover'],TENONS]
COLOR={'Tray':0,'Front_cover':1,'Rear_cover':1,**{n:2 for n in TENONS}}

def main():
    parts,refs,visual,dims=build(); report={'dimensions_mm':dims,'print_parts':{},'collisions_mm3':[]}
    printobjs={}; asmobjs=[]; transforms={}; y=10
    for row in PRINT_ROWS:
        x=10; depth=0
        for name in row:
            m=parts[name]; v,f=arrays(m); tm=trimesh.Trimesh(v,f,process=False)
            assert tm.is_watertight and tm.is_winding_consistent and tm.volume>0,name
            assert len(m.decompose())==1,(name,'disconnected bodies',len(m.decompose()))
            rotation=PRINT_ROTATION[name]
            pv=v@rotation.T
            translation=-pv.min(0)+np.array([x,y,0]);pv=pv+translation
            transforms[name]={"rotation":rotation.tolist(),"translation":translation.tolist()}
            x=pv[:,0].max()+12; depth=max(depth,pv[:,1].max())
            printobjs[name]=(name,pv,f,COLOR[name])
            report['print_parts'][name]={'volume_mm3':round(m.volume(),2),'print_extents_mm':np.ptp(pv,axis=0).round(3).tolist(),'one_watertight_body':True,'print_bounds_mm':[pv.min(0).tolist(),pv.max(0).tolist()]}
        y=depth+12
    printobjs=[printobjs[n] for n in parts]
    for name,m in parts.items():
        v,f=arrays(m);asmobjs.append((name,v,f,COLOR[name]))
    for n,(v,f) in visual.items():
        c=4 if n in ['Board','ESP_PCB'] else 6 if n=='PB503' else 5
        asmobjs.append((n,v,f,c))
    # All shell / hardware checks use conservative solids, not rendered images.
    for pn,p in parts.items():
        for rn,r in refs.items():
            vol=(p^r).volume()
            if vol>0.005: report['collisions_mm3'].append([pn,rn,round(vol,4)])
    for (an,a),(bn,b) in itertools.combinations(parts.items(),2):
        vol=(a^b).volume()
        if vol>.005:report['collisions_mm3'].append([an,bn,round(vol,4)])
    report['print_transforms']=transforms
    report['plate_max_mm']=np.vstack([x[1] for x in printobjs]).max(0).round(3).tolist()
    assert report['plate_max_mm'][0]<330 and report['plate_max_mm'][1]<320
    # Nominal contacts are zero-volume boundaries.
    report['intentional_interfaces']=['PCB bottom on ledges/pads Z=0','tray pin through PCB hole into cover-post socket; cover pad 0.20 above board',
        'front/rear hourglass tenons across the tray/cover split; rear tenon blocks open tail',
        'middle tenon across the front/rear cover seam, flat top and 45-degree notch']
    report['nominal_clearances_mm']={'pcb_side':BOARD_SIDE_CLEAR,'module_window':WINDOW_CLEAR,'bank':PB_CLEAR,'tenon_per_face':TENON_CLEAR,'pcb_top_play':BOARD_TOP_PLAY,'pcb_pin_in_hole_diametral':2*(HOLE_RADIUS-PIN_RADIUS),
        'pin_in_socket_diametral':2*(SOCKET_RADIUS-PIN_RADIUS),'pin_tip_to_socket_bottom':BOARD_TOP_PLAY+SOCKET_DEPTH-PIN_ABOVE_BOARD}
    report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'.pcba-workflow/pcb1_2-review-20261018/PCB1_2_review.step',H/'references/Braille_Module_Reference.pdf',H/'references/PCB1_2_module_socket_measurements.json',EVIDENCE]}
    (M/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    assert not report['collisions_mm3'],'Unwanted hardware/shell interference; see models/verification.json'
    # Only Bambu's native exporter may replace the public print project.
    # This hand-written archive is an intermediate input, never a deliverable.
    write3mf(M/'Handle_Print_Input.3mf',printobjs,transforms);write3mf(H/'Handle_Assembly.3mf',asmobjs)
    # Re-import the exact delivered archive; validate printable object meshes and position.
    scene=trimesh.load(M/'Handle_Print_Input.3mf',force='scene')
    for name,tm in scene.geometry.items():
        assert tm.is_watertight and tm.volume>0,name
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()








