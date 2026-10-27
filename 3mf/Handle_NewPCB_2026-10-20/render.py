"""Render the actual exported CAD meshes (no image generation or beauty geometry)."""
from pathlib import Path
import sys,os,tempfile,atexit
os.environ['PYTHONDONTWRITEBYTECODE']='1'
_runtime=tempfile.TemporaryDirectory(prefix='lingtouch-render-')
atexit.register(_runtime.cleanup)
os.environ['BLENDER_USER_RESOURCES']=_runtime.name
import numpy as np
import bpy
from mathutils import Vector
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H))
import build as B
OUT=H/'renders'; OUT.mkdir(exist_ok=True)
for old in OUT.glob('*.png'):
    if old.name!='13_bambu_support.png':old.unlink()  # that one is slice.py's
parts,refs,vis,dims=B.build()
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=16
sc.cycles.use_denoising=True
sc.render.resolution_x=1800;sc.render.resolution_y=1000;sc.render.resolution_percentage=100
sc.render.image_settings.file_format='PNG';sc.render.film_transparent=False
sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True
sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.82,.87,.91,1)
sc.world.node_tree.nodes['Background'].inputs[1].default_value=.6
sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=-.3
PART_COLOR={'Tray':(.055,.19,.24),'Front_cover':(.84,.86,.83),'Rear_cover':(.70,.74,.74),
            **{n:(.85,.46,.055) for n in B.TENONS}}
OBJ={}
def xyz(p): return Vector((p[0]/1000,p[1]/1000,p[2]/1000))
def add(n,v,f,col):
    me=bpy.data.meshes.new(n);me.from_pydata((v/1000).tolist(),[],f.tolist());me.update()
    ob=bpy.data.objects.new(n,me);sc.collection.objects.link(ob)
    mat=bpy.data.materials.new(n);mat.diffuse_color=(*col,1);mat.use_nodes=True
    bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*col,1);bs.inputs['Roughness'].default_value=.4
    ob.data.materials.append(mat);OBJ[n]=ob
    return ob
for n,m in parts.items():
    v,f=B.arrays(m);add(n,v,f,PART_COLOR[n])
for n,(v,f) in vis.items():
    col=(.035,.26,.12) if n in ['Board','ESP_PCB'] else (.30,.32,.34) if n=='PB503' else (.035,.045,.052)
    if n=='FPC_antenna':col=(.65,.32,.075)
    if n.startswith('C') or n.startswith('L'):col=(.43,.35,.18)
    add(n,v,f,col)
# Render-only raised dots show tactile positions; body top stays flush at FACE.
for n in ['U31','U32','U33','U34','U35','U36','U37','U38','U39','U48']:
    lo=np.array(refs[n].bounding_box()[:3]);hi=np.array(refs[n].bounding_box()[3:])
    x=(lo[0]+hi[0])/2;y=(lo[1]+hi[1])/2
    for dx in [-1.25,1.25]:
        for dy in [-2.5,0,2.5]:
            dot=B.cylinder(x+dx,y+dy,B.FACE-.1,.75,.55)
            v,f=B.arrays(dot);add(n+'_dot'+str(dx)+str(dy),v,f,(.74,.76,.70))
HARDWARE=[n for n in OBJ if n not in parts]

def area(n,pos,energy,size):
    ld=bpy.data.lights.new(n,'AREA');ld.energy=energy;ld.shape='DISK';ld.size=size
    ob=bpy.data.objects.new(n,ld);sc.collection.objects.link(ob);ob.location=xyz(pos)
    ob.rotation_euler=(xyz((90,0,0))-ob.location).to_track_quat('-Z','Y').to_euler()
area('Key',(60,-200,300),3,.32);area('Fill',(150,200,120),2,.3);area('Rim',(-70,30,200),2.5,.22)
camd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camd);sc.collection.objects.link(cam);sc.camera=cam
camd.type='ORTHO';camd.clip_start=.001;camd.clip_end=10
from PIL import Image,ImageDraw,ImageFont
FONT='C:/Windows/Fonts/msyh.ttc'
def caption(path,title,subtitle,size=(1800,1000)):
    im=Image.open(path).convert('RGB');canvas=Image.new('RGB',(size[0],size[1]+130),'#edf1f3');canvas.paste(im,(0,130))
    d=ImageDraw.Draw(canvas)
    d.text((55,18),title,fill='#182b38',font=ImageFont.truetype(FONT,34))
    d.text((55,72),subtitle,fill='#455c68',font=ImageFont.truetype(FONT,22))
    canvas.save(path)
def shot(name,eye,target,scale,shown,title='',subtitle='',up='Z'):
    for n,ob in OBJ.items(): ob.hide_render=n not in set(shown)
    cam.location=xyz(eye);cam.rotation_euler=(xyz(target)-cam.location).to_track_quat('-Z','Y' if up=='Z' else up).to_euler();camd.ortho_scale=scale/1000
    sc.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
    caption(sc.render.filepath,title,subtitle);print('RENDER',name,flush=True)
SHELLS=list(parts)
shot('01_exterior',(320,-350,285),(96,0,5),340,SHELLS,'外观：托盘 + 前盖 + 后盖 + 三根榫','前盖=杖口+模组区+45°坡；后盖=握把+尾段；缝在坡底，ESP 之前')
shot('02_side',(96,-450,7),(96,0,7),330,SHELLS,'侧面','杖口段比模组面低 3 mm；坡 45°；后盖顶面与尾段顶面同一平面')
shot('03_top',(96,0,450),(96,0,5),330,SHELLS,'俯视','三条模组窗 + 两道隔条，U48 单独开窗，SW1 圆孔')
shot('04_bottom',(96,0,-450),(96,0,5),330,SHELLS,'仰视：托盘底','托盘底面一个平面，四周原圆角')
shot('05_cane_mouth',(-400,0,7),(0,0,7),70,SHELLS,'杖口正视','Ø25 正圆，上下两半对称；上方三角槽是天线贴位')
shot('06_slope_seam',(59,-180,60),(62,0,14),60,SHELLS+HARDWARE,'坡与缝','45° 坡整段在前盖；缝在坡底；中间榫的槽穿两侧壁')
shot('15_tail_open',(B.TAIL+180,-65,60),(B.TAIL-7,0,5),70,SHELLS+['PB503'],'尾口敞开，后榫挡在充电宝后面','无尾墙；后榫横穿 Z=0 分缝')
shot('14_cover_interior',(300,-240,-230),(90,0,10),330,['Front_cover','Rear_cover','Middle_tenon'],'两块盖的内腔（从下往上看）','内腔没有填料；中间榫横跨两块盖')
shot('16_assembly_hardware',(320,-350,285),(96,0,5),340,['Tray','Middle_tenon','Front_tenon','Rear_tenon']+HARDWARE,'去掉两块盖后的硬件','板、模组、ESP、充电宝与托盘、三根榫的位置')

# True mesh sections through a side wall: each tenon with its two shells.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Microsoft YaHei'];plt.rcParams['axes.unicode_minus']=False
SECTION_COLOR={'Tray':'#245a72','Front_cover':'#9aa6a2','Rear_cover':'#5e6d6b',**{n:'#d78c17' for n in B.TENONS}}
fig,axes=plt.subplots(1,3,figsize=(17,6.5),dpi=160)
for ax,(n,label) in zip(axes,[('Front_tenon','前榫：连托盘与前盖，可拆'),('Middle_tenon','中间榫：连前盖与后盖，不拆'),('Rear_tenon','后榫：连托盘与后盖，可拆')]):
    sp=B.pin_spec(n);yy=-sp['half']+1.2 if sp['direction']>0 else sp['half']-1.2
    for k in ['Tray','Front_cover','Rear_cover',n]:
        v,f=B.arrays(parts[k]);tm=B.trimesh.Trimesh(v,f,process=False)
        section=tm.section(plane_normal=[0,1,0],plane_origin=[0,yy,0])
        if section:
            for i,line in enumerate(section.discrete):
                ax.plot(line[:,0],line[:,2],c=SECTION_COLOR[k],lw=2,label=k if i==0 else None)
    zc=(sp.get('seam_bottom',0)+sp.get('end_top',0))/2 if n=='Middle_tenon' else 0
    ax.axhline(0,c='#b64545',ls='--',lw=.8)
    if n=='Middle_tenon':ax.axvline(B.SEAM,c='#b64545',ls='--',lw=.8)
    ax.set(xlim=(sp['x']-7,sp['x']+7),ylim=(zc-7,zc+7),xlabel='X / mm（杖口→尾）',ylabel='Z / mm',title=label)
    ax.set_aspect('equal');ax.grid(alpha=.15);ax.legend(loc='upper left',fontsize=7)
fig.suptitle('三根榫的截面（侧壁内，真实网格）| 红虚线 = 分缝');fig.tight_layout();fig.savefig(OUT/'section_tenons.png');plt.close(fig)
# Long section on the axis: cane bore, slope, seam, middle tenon.
fig,ax=plt.subplots(figsize=(16,5),dpi=160)
for k in parts:
    v,f=B.arrays(parts[k]);tm=B.trimesh.Trimesh(v,f,process=False)
    section=tm.section(plane_normal=[0,1,0],plane_origin=[0,0,0])
    if section:
        for i,line in enumerate(section.discrete):ax.plot(line[:,0],line[:,2],c=SECTION_COLOR[k],lw=1.2,label=k if i==0 else None)
ax.set(xlim=(-40,100),ylim=(-12,29),xlabel='X / mm',ylabel='Z / mm',title='中线纵剖 Y=0：杖口、模组区、45° 坡、缝、中间榫');ax.set_aspect('equal');ax.grid(alpha=.15);ax.legend(fontsize=7,loc='lower right')
fig.tight_layout();fig.savefig(OUT/'section_long.png');plt.close(fig)
# Cross section through the cane mouth and the antenna recess.
fig,ax=plt.subplots(figsize=(7,7),dpi=160)
for k in ['Tray','Front_cover']:
    v,f=B.arrays(parts[k]);tm=B.trimesh.Trimesh(v,f,process=False)
    section=tm.section(plane_normal=[1,0,0],plane_origin=[-15,0,0])
    for i,line in enumerate(section.discrete):ax.plot(line[:,1],line[:,2],c=SECTION_COLOR[k],lw=1.6,label=k if i==0 else None)
b=np.array(refs['FPC_antenna'].bounding_box());ax.add_patch(plt.Rectangle((b[1],b[2]),b[4]-b[1],b[5]-b[2],color='#c56a12',label='FPC 天线'))
ax.set(xlabel='Y / mm',ylabel='Z / mm',title='杖口横剖 X=-15：Ø25 正圆 + 天线三角槽');ax.set_aspect('equal');ax.grid(alpha=.15);ax.legend(fontsize=8)
fig.tight_layout();fig.savefig(OUT/'section_cane.png');plt.close(fig)
# Both PCB mounting holes: tray post below the board, cover post above it.
fig,axes=plt.subplots(3,2,figsize=(12,16),dpi=150)
for col,(x,y) in enumerate(B.HOLES):
    cover='Front_cover' if x<B.SEAM else 'Rear_cover';side='前孔' if col==0 else '后孔'
    for ax,(n,z,label) in zip(axes[:2,col],[(cover,3.0,'盖子，板面上方 0.8 mm（中间是接销的孔）'),('Tray',-3.0,'托盘，板底下 3 mm')]):
        for q in parts[n].slice(z).to_polygons():ax.fill(q[:,0],q[:,1],color='#9fc0cc' if n=='Tray' else '#c9d1ce',ec='#33454d',lw=1)
        for q in refs['Board'].slice(1.0).to_polygons():
            q=np.vstack([q,q[:1]]);ax.plot(q[:,0],q[:,1],c='#21844f',lw=1,ls=':')
        ax.add_patch(plt.Circle((x,y),B.HOLE_RADIUS,fill=False,ec='r',lw=1.5))
        ax.set(xlim=(x-6,x+6),ylim=(y-6,y+6),title=side+' · '+label);ax.set_aspect('equal');ax.grid(alpha=.2)
    # Vertical cut through the hole centre, along X.
    ax=axes[2,col]
    for n,c,label in [('Tray','#245a72','托盘（含销）'),(cover,'#7d8a86','盖子（含接销孔）'),('Board','#21844f','PCB')]:
        m=parts.get(n,refs.get(n));v,f=B.arrays(m);tm=B.trimesh.Trimesh(v,f,process=False)
        s=tm.section(plane_normal=[0,1,0],plane_origin=[0,y,0])
        if s:
            for i,line in enumerate(s.discrete):ax.plot(line[:,0],line[:,2],c=c,lw=1.6,label=label if i==0 else None)
    ax.legend(fontsize=8,loc='lower right')
    ax.set(xlim=(x-5,x+5),ylim=(-4,8),xlabel='X / mm',ylabel='Z / mm',title=side+' · 过孔中心的竖剖：托盘销 Ø1.0 穿板，伸进盖子 Ø1.3 孔')
    ax.set_aspect('equal');ax.grid(alpha=.2)
fig.suptitle('PCB 安装孔 | 红圈 = 板上 Ø1.2 孔，绿点线 = PCB 外形');fig.tight_layout();fig.savefig(OUT/'section_pcb_holes.png');plt.close(fig)
# Exact top-face contours, overlaid with native PCB module top footprints.
fig,ax=plt.subplots(figsize=(13,9),dpi=160)
for q in parts['Front_cover'].slice(B.FACE-.15).to_polygons():
    a=np.sum(q[:,0]*np.roll(q[:,1],-1)-q[:,1]*np.roll(q[:,0],-1))/2
    ax.fill(q[:,0],q[:,1],color='#c3ccc9' if a>0 else 'white',edgecolor='#415b66',lw=1)
from matplotlib.patches import Rectangle
for n,a,b in B.native_references()[2]:
    ax.add_patch(Rectangle(a,b[0]-a[0],b[1]-a[1],fill=False,ec='#d1582c',lw=1.2,ls='--'))
    ax.text((a[0]+b[0])/2,(a[1]+b[1])/2,n,ha='center',va='center',fontsize=9)
ax.set(xlim=(9,59),ylim=(-21,21),xlabel='X / mm',ylabel='Y / mm',title='前盖顶面（模组区）| 橙虚线 = 模组顶面 6×8.2 mm')
ax.set_aspect('equal');ax.grid(alpha=.12);fig.tight_layout();fig.savefig(OUT/'03_top_windows.png');plt.close(fig)

# Specified print poses, as exported.
import json
tf=json.loads((H/'models/verification.json').read_text())['print_transforms']
sc.render.resolution_x=1200;sc.render.resolution_y=650
canvas=Image.new('RGB',(2400,2520),'#edf1f3');draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype(FONT,36);small=ImageFont.truetype(FONT,26)
labels=[('Tray','托盘','底面贴床'),('Front_cover','前盖','模组面贴床（顶朝下）'),('Rear_cover','后盖','握把顶面贴床（顶朝下）'),
        ('Front_tenon','前榫','宽平面贴床'),('Rear_tenon','后榫','宽平面贴床'),('Middle_tenon','中间榫','竖立，截面贴床')]
for i,(name,label,cap) in enumerate(labels):
    for ob in OBJ.values():ob.hide_render=True
    v,f=B.arrays(parts[name]);v=v@np.array(tf[name]['rotation']).T+np.array(tf[name]['translation'])
    add('PRINT_'+name,v,f,PART_COLOR[name])
    bed=B.box([v[:,0].min()-8,v[:,1].min()-8,-.6],[v[:,0].max()+8,v[:,1].max()+8,0]);bv,bf=B.arrays(bed);add('BED_'+name,bv,bf,(.25,.27,.29))
    lo=v.min(0);hi=v.max(0);center=(lo+hi)/2;length=max(hi-lo)
    cam.location=xyz(center+np.array([length*.35,-length*.8,length*.6]));cam.rotation_euler=(xyz(center)-cam.location).to_track_quat('-Z','Y').to_euler();camd.ortho_scale=length*(2.0 if name=='Middle_tenon' else 1.3)/1000
    path=Path(_runtime.name)/f'part{i}.png';sc.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    left=(i%2)*1200;top=(i//2)*840;canvas.paste(Image.open(path).convert('RGB'),(left,top))
    draw.text((left+40,top+665),label,font=font,fill='#182b38');draw.text((left+40,top+722),cap,font=small,fill='#455c68')
    draw.text((left+40,top+767),' x '.join(f'{a:.1f}' for a in hi-lo)+' mm',font=small,fill='#455c68')
canvas.save(OUT/'11_print_poses.png')
