"""Build a true right hand by reflecting the source LEFT hand and its full rig.

Source hand: Emma L. D. Lieker, CC BY-NC 4.0; see inputs/EmmaLieker_LICENSE.txt.
All study coordinates and reports use the original handle CAD frame in millimetres.
"""
from pathlib import Path
import sys, json, hashlib, argparse, math
import numpy as np
import bpy
from mathutils import Matrix, Vector
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from source import read_source

FINGERS=['index','midd','ring','pinky']
TARGET=np.array([64.,25.4,0.])
PARAMETER_COUNT=35
RIGHT_REFLECTION=np.diag([1.,1.,-1.])
GRIP_WIDTH=None

def material(name,color,roughness=.55):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    node=m.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value=(*color,1)
    node.inputs['Roughness'].default_value=roughness
    return m

def evaluated_vertices(o):
    dg=bpy.context.evaluated_depsgraph_get();eo=o.evaluated_get(dg);me=eo.to_mesh()
    v=np.array([list(eo.matrix_world@q.co) for q in me.vertices])*1000
    eo.to_mesh_clear();return v

def prepare():
    bpy.ops.wm.open_mainfile(filepath=str(HERE/'inputs/EmmaLieker_Hand.blend'),load_ui=False,use_scripts=False)
    rig=bpy.data.objects['Rig'];hand=bpy.data.objects['Hand'];nails=bpy.data.objects['Nails']
    rig.animation_data_clear()
    for pb in rig.pose.bones:
        pb.rotation_mode='XYZ';pb.rotation_euler=(0,0,0)
        for c in pb.constraints:
            if c.type=='COPY_ROTATION': c.mute=True
    bpy.context.view_layer.update()
    v=np.array([list(q.co) for q in hand.data.vertices]);hand.data.calc_loop_triangles()
    f=np.array([list(q.vertices) for q in hand.data.loop_triangles])
    normals=np.array([list(q.normal) for q in hand.data.vertices])
    names=[b.name for b in rig.data.bones];idx={n:i for i,n in enumerate(names)}
    weights=np.zeros((len(v),len(names)))
    for i,q in enumerate(hand.data.vertices):
        for g in q.groups:
            gn=hand.vertex_groups[g.group].name
            if gn in idx:weights[i,idx[gn]]=g.weight
    print('WEIGHT RANGE',float(weights.sum(1).min()),float(weights.sum(1).max()),flush=True)
    assert np.all(weights.sum(1)>0), 'Unweighted hand vertices'
    weights/=weights.sum(1)[:,None]
    dominant=np.array(names)[weights.argmax(1)]
    rest=np.array([np.array(rig.data.bones[n].matrix_local) for n in names])
    inverse=np.linalg.inv(rest)
    parents=[idx.get(rig.data.bones[n].parent.name,-1) if rig.data.bones[n].parent else -1 for n in names]
    wrist=np.array(rig.data.bones['radius_ulna'].tail_local)
    direction=np.array(rig.data.bones['midd_dist'].tail_local)-wrist;direction/=np.linalg.norm(direction)
    tipv=v[dominant=='midd_dist'];tip=tipv[np.argmax((tipv-wrist)@direction)]
    uniform=180./((tip-wrist)@direction)
    mcpz=np.mean([rig.data.bones[n+'_prox'].head_local.z for n in FINGERS])
    palm_mask=(abs(v[:,2]-mcpz)<.5)&~np.char.startswith(dominant,'thumb')
    palm=v[palm_mask]
    scales=np.array([78./np.ptp(palm[:,0]),27.6/np.ptp(palm[:,1]),uniform])
    # Keep the longitudinal projected hand-length datum at 180 mm after transverse calibration.
    scales[2]+=(180.-np.dot((tip-wrist)*scales,direction))/(tip[2]-wrist[2])/direction[2]
    pads={}
    for finger in FINGERS+['thumb']:
        name=finger+'_dist';b=rig.data.bones[name]
        along=(v-np.array(b.head_local))@(np.array(b.tail_local)-np.array(b.head_local))/b.length**2
        mask=(weights[:,idx[name]]>.25)&(along>.25)&(along<.95)&(normals[:,1]<-.35)
        ids=np.flatnonzero(mask)
        assert len(ids)>=3,(finger,len(ids))
        pads[finger]=ids
    p_mask=(v[:,2]>7)&(v[:,2]<10)&(v[:,0]>-5)&(v[:,0]<2)&(normals[:,1]<-.65)&~np.char.startswith(dominant,'thumb')
    pads['palm']=np.flatnonzero(p_mask)
    for finger in FINGERS:
        for part in ['prox','midd']:
            name=finger+'_'+part;b=rig.data.bones[name]
            along=(v-np.array(b.head_local))@(np.array(b.tail_local)-np.array(b.head_local))/b.length**2
            pads[name]=np.flatnonzero((weights[:,idx[name]]>.25)&(along>.15)&(along<.85)&(normals[:,1]<-.35))
    regions={
        'central_palm':(v[:,2]>7)&(v[:,2]<10)&(v[:,0]>-4)&(v[:,0]<1)&(normals[:,1]<-.65),
        'distal_palm_mcp':(v[:,2]>9.5)&(v[:,2]<11.8)&(v[:,0]>-6.2)&(v[:,0]<3.2)&(normals[:,1]<-.6),
        'thenar':(v[:,0]>-6.5)&(v[:,0]<-2.7)&(v[:,2]>4.7)&(v[:,2]<8.5)&(normals[:,1]<-.4),
        'hypothenar':(v[:,0]>0)&(v[:,0]<3.3)&(v[:,2]>4.7)&(v[:,2]<9.2)&(normals[:,1]<-.4)}
    regions={k:np.flatnonzero(mask) for k,mask in regions.items()}
    pad_faces={k:f[np.sum(np.isin(f,ids),axis=1)>=2] for k,ids in pads.items()}
    skin=material('Study skin',(0.53,0.30,0.19),.65)
    nail=material('Study nails',(0.65,0.47,0.36),.4)
    for o,m in [(hand,skin),(nails,nail)]:
        o.data.materials.clear();o.data.materials.append(m)
        for p in o.data.polygons:p.use_smooth=True
    root=bpy.data.objects.new('Adult right hand placement',None);bpy.context.collection.objects.link(root)
    rig.parent=root
    root['hand_length_mm']=180.;root['palm_breadth_mm']=78.;root['palm_thickness_datum_mm']=27.6
    root['source']='Emma L. D. Lieker / anatomical-hand-model, CC BY-NC 4.0'
    calibration={'hand_length_mm':float(np.dot((tip-wrist)*scales,direction)),
                 'palm_breadth_mm':float(np.ptp(palm[:,0])*scales[0]),
                 'palm_thickness_datum_mm':float(np.ptp(palm[:,1])*scales[1]),
                 'source_to_mm_xyz':scales.tolist(),'wrist_landmark_source':wrist.tolist(),
                 'middle_tip_source':tip.tolist(),
                 'definition':'Model wrist landmark to middle fingertip projected along the open-hand axis; palm breadth/thickness measured in MCP band excluding thumb. Generic adult calibration, not an individual scan.',
                 'reference':'https://thescipub.com/pdf/ajeassp.2016.877.888.pdf',
                 'changes':'Source LEFT hand reflected together with the complete rig to form a true RIGHT hand; adult calibration, neutral material and independent FK. Original source retained unchanged.',
                 'source_handedness':'left','delivered_handedness':'right',
                 'handedness_verification':'Actual palm-facing view: thumb at image right, little finger at image left. Full rig, skin and nails are reflected together; posed hand sits on CAD-negative-Z side.'}
    return dict(rig=rig,hand=hand,nails=nails,root=root,v=v,f=f,normals=normals,names=names,idx=idx,
                weights=weights,rest=rest,inverse=inverse,parents=parents,pads=pads,pad_faces=pad_faces,regions=regions,scales=scales,calibration=calibration)

def rotations(p):
    r={}
    for i,f in enumerate(FINGERS):
        for j,s in enumerate(['prox','midd','dist']):r[f+'_'+s]=np.array([p[31+i] if j==0 else 0.,0.,p[6+3*i+j]])
        r[f+'_meta']=np.array([0.,0.,p[27+i]])
    a=p[18:27]
    r['thumb_trapez']=np.array([a[0],0,a[1]])
    r['thumb_meta']=np.array(a[2:5])
    r['thumb_prox']=np.array(a[5:8])
    r['thumb_dist']=np.array([0,0,a[8]])
    return r

def pose_matrices(data,p):
    pose=[];rr=rotations(p)
    for i,n in enumerate(data['names']):
        delta=np.eye(4);delta[:3,:3]=Rotation.from_euler('xyz',rr.get(n,[0,0,0]),degrees=True).as_matrix()
        par=data['parents'][i]
        if par<0:m=data['rest'][i]@delta
        else:m=pose[par]@data['inverse'][par]@data['rest'][i]@delta
        pose.append(m)
    return np.array(pose)

def skin(data,p,return_matrices=False,source_space=False):
    sm=pose_matrices(data,p)@data['inverse']
    weighted=np.einsum('vb,bij->vij',data['weights'],sm)
    vv=np.einsum('vij,vj->vi',weighted,np.column_stack([data['v'],np.ones(len(data['v']))]))[:,:3]
    R=Rotation.from_euler('xyz',p[3:6],degrees=True).as_matrix()
    vv=(vv*data['scales'])@R.T+p[:3]
    if not source_space:vv=vv@RIGHT_REFLECTION.T
    if return_matrices:return vv,weighted,R
    return vv

def thumb_axis(data,p,source_space=False):
    m=pose_matrices(data,p)[data['idx']['thumb_dist']]
    R=Rotation.from_euler('xyz',p[3:6],degrees=True).as_matrix()
    axis=(m[:3,1]*data['scales'])@R.T
    if not source_space:axis=RIGHT_REFLECTION@axis
    return axis/np.linalg.norm(axis)

def box_sdf(p,lo,hi):
    lo=np.array(lo);hi=np.array(hi);q=np.abs(p-(lo+hi)/2)-(hi-lo)/2
    return np.linalg.norm(np.maximum(q,0),axis=1)+np.minimum(np.max(q,axis=1),0)

def pad_normal(data,v,k):
    tri=v[data['pad_faces'][k]]
    n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]).sum(0)
    return n/np.linalg.norm(n)

def handle_sdf(p):
    # Conservative closed exterior for the fitting stage; final checks use exported faces.
    q=np.abs(p[:,2])-23
    floor=-np.sqrt(np.maximum(31**2-np.minimum(np.abs(p[:,2]),31)**2,0))
    cross=np.maximum.reduce([q,p[:,1]-23.5,floor-p[:,1]])
    def end(x0,x1):return np.maximum(cross,np.maximum(x0-p[:,0],p[:,0]-x1))
    front=end(0,68);tail=end(220,230)
    if GRIP_WIDTH is None:middle=box_sdf(p,[68,-12,-23],[220,23.5,23])
    else:
        def smooth(t):
            t=np.clip(t,0,1);return t*t*(3-2*t)
        influence=smooth((p[:,0]-70)/15)*smooth((195-p[:,0])/20)*smooth((-p[:,1]-4.5)/4)
        hw=23-(23-GRIP_WIDTH/2)*influence
        middle=np.maximum.reduce([np.abs(p[:,2])-hw,-12-p[:,1],p[:,1]-23.5,68-p[:,0],p[:,0]-220])
    tube=np.maximum(np.hypot(p[:,1],p[:,2])-14,np.maximum(-40-p[:,0],p[:,0]))
    return np.minimum.reduce([front,middle,tail,tube])

def fit(data,warmstart=None):
    # Rebuild the side-palm grasp, rather than rotating the rejected flat-palm pose.
    base=np.array([170.4735,86.3008,43.0905,81.6697,-7.0907,-20.]+[45,70,40]*4+
                  [7.8652,44.5325,-10,20,-20,10,10,-20,-10]+[0,0,3,6]+[0,0,0,0],float)
    lo=np.array([130,50,25,65,-20,-35]+[5,10,0]*4+[-20,-30,-10,-20,-20,-10,-10,-20,-10]+[-5,-5,0,0]+[-12]*4,float)
    hi=np.array([205,115,85,110,15,5]+[110,115,55]*4+[20,175,35,20,55,10,10,80,90]+[6,6,12,18]+[12]*4,float)
    # Longer fingers should flex through the PIP instead of staying straight
    # while the MCP alone hooks them underneath the shell.
    lo[10]=40.;lo[13]=40.
    collision_weight=6.;margin=.15
    edges=np.unique(np.sort(np.concatenate([data['f'][:,[0,1]],data['f'][:,[1,2]],data['f'][:,[2,0]]]),axis=1),axis=0)
    def residual(p):
        # Symmetric handle fit in source-left coordinates, then the entire result
        # is reflected to its true right-side physical placement for delivery.
        v,weighted,R=skin(data,p,True,source_space=True);sdf=handle_sdf(v)
        centroid_sdf=handle_sdf(v[data['f']].mean(1))
        edge_sdf=handle_sdf(v[edges].mean(1))
        thumb=v[data['pads']['thumb']].mean(0)
        # Use actual deformed skin triangles; weighted rest normals can flip in a strong curl.
        direction=pad_normal(data,v,'thumb')
        contacts=[max(np.quantile(sdf[data['pads'][f]],.15)-.6,0)*2 for f in FINGERS]
        # Both lower finger surfaces and the tips support the handle. A tip alone
        # close to the shell is insufficient evidence of a wrapped grasp.
        under_contacts=[max(np.quantile(sdf[data['pads'][f+'_prox']],.15)-1.2,0) for f in FINGERS]
        mid_contacts=[max(np.quantile(sdf[data['pads'][f+'_midd']],.15)-1.0,0)*2 for f in FINGERS]
        below=[max(v[data['pads'][f+'_midd'],1].mean()+3,0) for f in FINGERS]
        # Shorter outer fingers support the underside; middle and ring curl back
        # up the far side. Do not stretch every fingertip to the same far-wall point.
        narrow=GRIP_WIDTH/2 if GRIP_WIDTH else 23
        opposite=[max(v[data['pads'][f],2].mean()+z,0) for f,z in zip(FINGERS,[min(16,narrow),23,23,min(13,narrow)])]
        tipheight=[(v[data['pads'][f],1].mean()-y)*.35 for f,y in zip(FINGERS,[-10,0,-2,-12])]
        tipnormals=np.concatenate([(pad_normal(data,v,f)-normal)*6 for f,normal in
                                  zip(FINGERS,[[0,.75,.66],[0,0,1],[0,.2,.98],[0,1,0]])])
        joint_balance=[max(p[6+3*i+2]*.9-p[6+3*i+1],0)*.5 for i in range(4)]
        joint_balance.extend([(p[9]-60)*.12,(p[12]-60)*.12])
        palm=max(np.min(sdf[data['pads']['palm']])-.6,0)
        palmids=data['pads']['palm']
        pn=pad_normal(data,v,'palm')
        prior=(p[6:]-base[6:])*.025
        palmpos=v[palmids].mean(0)
        support=[max(np.quantile(sdf[ids],.10)-gap,0)*weight for (name,ids),gap,weight in
                 zip(data['regions'].items(),[3.,1.2,1.5,1.],[3.,4.,3.,3.])]
        touch=(v[data['pads']['thumb'],1].min()-24.0)*4
        axis=thumb_axis(data,p,source_space=True)
        return np.r_[np.maximum(margin-sdf,0)*collision_weight,np.maximum(margin-centroid_sdf,0)*collision_weight,
                     np.maximum(margin-edge_sdf,0)*collision_weight,
                     (thumb-TARGET)*3,(direction-[.10,-.94,-.32])*35,(axis-[-1,0,0])*30,
                     touch,contacts,under_contacts,mid_contacts,below,opposite,tipheight,tipnormals,palm,support,
                     (pn-[.03,-.40,-.92])*10,(palmpos-[130,5,27])*.5,joint_balance,prior]
    best=None
    starts=[]
    starts.append(base)
    if warmstart and Path(warmstart).exists():
        saved=json.loads(Path(warmstart).read_text())
        if len(saved['parameters'])==PARAMETER_COUNT:starts=[np.array(saved['parameters'])]
    elif (HERE/'grip_pose.json').exists():
        saved=json.loads((HERE/'grip_pose.json').read_text())
        if len(saved['parameters'])==PARAMETER_COUNT and 'side-palm' in saved.get('grip',''):starts.insert(0,np.array(saved['parameters']))
    for start in starts:
        angle=start[3]
        start=np.clip(start,lo+.001,hi-.001)
        result=least_squares(residual,start,bounds=(lo,hi),max_nfev=140,ftol=1e-5,xtol=1e-5,gtol=1e-5,diff_step=1e-4)
        vv=skin(data,result.x,source_space=True);sd=handle_sdf(vv)
        score=np.sum(result.fun**2)
        print('FIT',angle,'cost',score,'min exterior',sd.min(),'thumb',vv[data['pads']['thumb']].mean(0).tolist(),flush=True)
        ranking=score+max(-sd.min(),0)*1000
        if best is None or ranking<best[0]:best=(ranking,result.x)
    collision_weight=40.;margin=.3
    cleared=least_squares(residual,best[1],bounds=(lo,hi),max_nfev=100,ftol=1e-6,xtol=1e-6,gtol=1e-6,diff_step=1e-4)
    vv=skin(data,cleared.x,source_space=True)
    print('CLEARANCE',float(handle_sdf(vv).min()),'thumb',vv[data['pads']['thumb']].mean(0).tolist(),flush=True)
    return cleared.x

def apply_pose(data,p,neutral=False):
    R=Rotation.from_euler('xyz',p[3:6],degrees=True).as_matrix()
    m=np.eye(4);m[:3,:3]=R@np.diag(data['scales']/1000);m[:3,3]=p[:3]/1000
    reflection=np.diag([-1.,1.,1.]) if neutral else RIGHT_REFLECTION
    m[:3,:3]=reflection@m[:3,:3];m[:3,3]=reflection@m[:3,3]
    data['root'].matrix_world=Matrix(m.tolist())
    data['root']['handedness']='RIGHT: full source-left rig/skin/nails reflection'
    rr=rotations(p)
    for n,pb in data['rig'].pose.bones.items():pb.rotation_euler=np.deg2rad(rr.get(n,[0,0,0]))
    bpy.context.view_layer.update()

def add_handle(redesigned=None):
    import xml.etree.ElementTree as ET
    rows,members=read_source();settings=ET.fromstring(members['Metadata/model_settings.config'])
    shell=material('Original handle shell',(0.68,0.72,0.74),.62)
    objs=[]
    for row in rows:
        obj=settings.find("object[@id='%s']"%row['build_object_id'])
        offset=np.array([float(obj.find("part/metadata[@key='source_offset_%s']"%k).get('value')) for k in 'xyz'])
        if redesigned:
            with np.load(Path(redesigned)/(row['name']+'.npz')) as q:v=q['v']/1000;faces=q['f']
            prefix='Redesigned handle '
        else:v=(row['v']+offset)/1000;faces=row['f'];prefix='Original handle '
        me=bpy.data.meshes.new(prefix+row['name']);me.from_pydata(v.tolist(),[],faces.tolist());me.update()
        o=bpy.data.objects.new(prefix+row['name'],me);bpy.context.collection.objects.link(o);o.data.materials.append(shell)
        o['unchanged_original_mesh']=not bool(redesigned);o['source_offset_mm']=offset.tolist();objs.append(o)
    black=material('Touch face reference',(0.035,0.045,0.05),.6)
    for x in [51.,57.5,64.,70.5,77.]:
        for z in [-11.,0.,11.]:
            bpy.ops.mesh.primitive_cube_add(size=1,location=(x/1000,13.5/1000,z/1000))
            o=bpy.context.object;o.name='Touch-face datum';o.dimensions=(.006,.020,.0082);o.data.materials.append(black)
            o['scope']='Face-height reference for grip study, not full PCB/module assembly validation.'
    return objs

def camera(name,location,target,ortho):
    d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o)
    o.location=location;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    d.type='ORTHO';d.ortho_scale=ortho;d.clip_start=.001;return o

def setup_render():
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=64;scene.cycles.use_denoising=True
    scene.render.resolution_x=1200;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    scene.world=bpy.data.worlds.new('Study world');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.18,.20,.22,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
    for name,loc,power,size in [('Key',(.05,.45,.4),5,.35),('Fill',(.15,.08,-.4),3,.35),('Rim',(.3,.25,.1),4,.25)]:
        d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size
        o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((.12,.025,0))-o.location).to_track_quat('-Z','Y').to_euler()
    scene.view_settings.view_transform='AgX'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--refit',action='store_true');parser.add_argument('--neutral',action='store_true');parser.add_argument('--fit-only',action='store_true');parser.add_argument('--quick',action='store_true');parser.add_argument('--grip-width',type=float);parser.add_argument('--redesigned');parser.add_argument('--output-dir');args=parser.parse_args()
    global GRIP_WIDTH
    GRIP_WIDTH=args.grip_width
    output=(Path(args.output_dir) if args.output_dir else HERE).resolve();output.mkdir(exist_ok=True,parents=True)
    if args.redesigned:args.redesigned=str(Path(args.redesigned).resolve())
    HERE.mkdir(exist_ok=True)
    data=prepare();(HERE/'calibration.json').write_text(json.dumps(data['calibration'],indent=2),encoding='utf8')
    if args.neutral:
        p=np.zeros(PARAMETER_COUNT);p[:3]=[0,0,0];apply_pose(data,p,neutral=True)
        setup_render()
        target=Vector((.028,0,.105))
        for name,loc in [('Key',(.15,-.35,.30)),('Fill',(-.2,-.2,.15))]:
            o=bpy.data.objects[name];o.location=loc;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
        bpy.context.scene.camera=camera('Adult hand palm',(.028,-.40,.105),target,.32)
        bpy.context.scene.render.filepath=str(HERE/'AdultRightHand.png');bpy.ops.render.render(write_still=True)
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'AdultRightHand.blend'),check_existing=False)
        print('CALIBRATION',json.dumps(data['calibration']),flush=True);return
    posefile=output/'grip_pose.json'
    if args.refit or not posefile.exists():
        p=fit(data,posefile);posefile.write_text(json.dumps({'parameters':p.tolist(),'thumb_target_cad_mm':TARGET.tolist(),'handedness':'right through full-rig reflection','grip':'right side-palm thumb grasp; palm on negative Z, thumb forward toward cane, fingers underneath and around opposite side','grip_width_mm':GRIP_WIDTH},indent=2),encoding='utf8')
    else:p=np.array(json.loads(posefile.read_text())['parameters'])
    assert len(p)==PARAMETER_COUNT,'Saved pose uses the rejected flat-palm parameter layout'
    if args.fit_only:return
    apply_pose(data,p);add_handle(args.redesigned);setup_render()
    software=skin(data,p);actual=evaluated_vertices(data['hand'])
    error=float(np.max(np.linalg.norm(software-actual,axis=1)))
    print('SKIN READBACK ERROR MM',error,flush=True)
    assert error<.01,'Exported skin differs from fitting skin'
    if args.quick:bpy.context.scene.cycles.samples=16
    for name,loc in [('Grip_Overview',(-.22,.33,-.32)),('Grip_Top',(.12,.6,0)),('Grip_Underside',(.14,-.55,.16)),('Grip_End',(.65,.03,0))]:
        o=camera(name,loc,(.12,.025,0),.34)
        bpy.context.scene.camera=o;bpy.context.scene.render.filepath=str(output/(name+'.png'));bpy.ops.render.render(write_still=True)
    bpy.context.scene.camera=bpy.data.objects['Grip_Overview']
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output/('AdultRightHand_RedesignedHandle.blend' if args.redesigned else 'AdultHand_OriginalHandle.blend')),check_existing=False)
    report={'calibration':data['calibration'],'skin_readback_max_mm':error,'thumb_pad_cad_mm':actual[data['pads']['thumb']].mean(0).tolist(),
            'thumb_distal_axis_cad':thumb_axis(data,p).tolist(),'palm_pad_cad_mm':actual[data['pads']['palm']].mean(0).tolist(),
            'hand_bounds_cad_mm':[actual.min(0).tolist(),actual.max(0).tolist()],
            'minimum_fitting_exterior_sdf_mm':float(handle_sdf(actual).min()),
            'finger_contact_proxy_mm':{f:float(handle_sdf(actual[data['pads'][f]]).min()) for f in FINGERS},
            'scope':'Candidate right-hand placement on the selected enclosure; skin readback checked. Final exact surface inspection remains required.',
            'source_hand_sha256':hashlib.sha256((HERE/'inputs/EmmaLieker_Hand.blend').read_bytes()).hexdigest(),
            'handedness':'right, verified by full-reflection and actual thumb/palm/nail arrangement','grip_width_mm':GRIP_WIDTH}
    (output/'placement.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('DONE',json.dumps(report),flush=True)

if __name__=='__main__':main()
