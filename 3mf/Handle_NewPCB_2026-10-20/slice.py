"""Bambu system-default H2C PLA 0.4 / 0.20 Standard slicing, support enabled.
Support is reported per part and per location, split into what Hsinlung
accepted and everything else."""
from pathlib import Path
import json,re,sys,subprocess,zipfile,hashlib,math
from collections import defaultdict
H=Path(__file__).resolve().parent;M=H/'models'
EXE=Path('D:/Bambu Studio/bambu-studio.exe');PROFILES=EXE.parent/'resources/profiles/BBL'
def profiles():
    paths={p.stem:p for p in PROFILES.rglob('*.json')}
    def resolve(name):
        d=json.loads(paths[name].read_text(encoding='utf8'));out={}
        if d.get('inherits'):out.update(resolve(d['inherits']))
        for n in d.get('include',[]):out.update(resolve(n))
        out.update({k:v for k,v in d.items() if k not in ['inherits','include']});return out
    result={}
    for file,name in [('h2c_machine.json','Bambu Lab H2C 0.4 nozzle'),('h2c_process.json','0.20mm Standard @BBL H2C'),('h2c_pla.json','Bambu PLA Basic @BBL H2C')]:
        d=resolve(name)
        if file=='h2c_process.json':d['enable_support']='1'
        (M/file).write_text(json.dumps(d,indent=2),encoding='utf8');result.update(d)
    return result

def run():
    profiles()
    source=M/'Handle_Print_Input.3mf'
    assert source.exists(),'Run build.py first; the public project is not a build input.'
    args=[str(EXE),'--debug','2','--load-settings',str(M/'h2c_machine.json')+';'+str(M/'h2c_process.json'),'--load-filaments',str(M/'h2c_pla.json'),'--slice','0','--arrange','0','--orient','0','--outputdir',str(M),'--export-3mf','Handle_H2C_Sliced.3mf',str(source)]
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    subprocess.run(args,check=True,cwd=H)
    invocation={'argv':args,'input_sha256':digest,'output_sha256':hashlib.sha256((M/'Handle_H2C_Sliced.3mf').read_bytes()).hexdigest()}
    (M/'slice_command.json').write_text(json.dumps(invocation,indent=2),encoding='utf8')
    r=json.loads((M/'result.json').read_text());assert r['return_code']==0 and r['sliced_plates']
    (M/'bambu_slice_result.json').write_text(json.dumps(r,indent=2),encoding='utf8')
    (M/'result.json').unlink(missing_ok=True);(M/'plate_1.gcode').unlink(missing_ok=True)

def audit():
    invocation=json.loads((M/'slice_command.json').read_text())
    native=M/'Handle_H2C_Sliced.3mf'
    if not native.exists():native=H/'Handle_Print_H2C.3mf'
    assert invocation['output_sha256']==hashlib.sha256(native.read_bytes()).hexdigest()
    source=M/'Handle_Print_Input.3mf'
    if source.exists():assert invocation['input_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    with zipfile.ZipFile(native) as z:
        gcode=z.read('Metadata/plate_1.gcode').decode('utf8');settings=json.loads(z.read('Metadata/project_settings.config'));config=z.read('Metadata/model_settings.config').decode('utf8')
    assert 'support_blocker' not in config and 'support_enforcer' not in config
    assert settings['printer_model']=='Bambu Lab H2C' and float(settings['layer_height'])==.2
    assert settings['filament_type'][0]=='PLA' and all(float(n)==.4 for n in settings['nozzle_diameter'])
    defaults=profiles()
    skip=['name','from','type','instantiation','setting_id','description','compatible_printers','print_settings_id','enable_prime_tower']
    def norm(v):
        if isinstance(v,list):return [norm(a) for a in v]
        try:return float(str(v).rstrip('%'))
        except ValueError:return v
    differences={k:[defaults[k],settings.get(k)] for k in json.loads((M/'h2c_process.json').read_text()).keys() if k in settings and norm(settings[k])!=norm(defaults[k]) and k not in skip}
    assert not differences,differences
    role='';relative=True;last_e=0.;xyz=[0.,0.,0.];lengths=defaultdict(float);bounds=[];support_segments=[];support_weights=[];object_segments=[];interfaces=defaultdict(float);interface_points=[];part_extrusions=[]
    for line in gcode.splitlines():
        if line.startswith('; FEATURE:'):role=line.split(':',1)[1].strip()
        code=line.split(';',1)[0].strip()
        if not code:continue
        cmd=code.split()[0]
        if cmd=='M83':relative=True
        if cmd=='M82':relative=False
        d={k:float(v) for k,v in re.findall(r'([XYZE])([-+]?(?:[0-9]*[.])?[0-9]+)',code)}
        if cmd=='G92':
            if 'E' in d:last_e=d['E']
            continue
        if cmd not in ['G0','G1','G2','G3']:continue
        to=[d.get(k,xyz[i]) for i,k in enumerate('XYZ')];e=d.get('E',0) if relative else d.get('E',last_e)-last_e
        if 'E' in d:last_e=d['E']
        if e>0 and (to[:2]!=xyz[:2] or cmd in ['G2','G3']):
            lengths[role]+=e
            if role!='Custom':part_extrusions.append(((xyz[1]+to[1])/2,e,[(a+b)/2 for a,b in zip(xyz,to)]))
            if role.startswith('Support'):
                bounds.extend([xyz,to]);support_segments.append([xyz.copy(),to.copy()]);support_weights.append(e*float(1))
                if role=='Support interface':
                    interfaces[round(to[2],2)]+=e;interface_points.append(to.copy())
            elif role not in ['Custom','Brim']:object_segments.append([xyz.copy(),to.copy()])
        xyz=to
    factor=math.pi*(float(settings['filament_diameter'][0])/2)**2*float(settings['filament_density'][0])/1000
    grams={k:v*factor for k,v in lengths.items()};support=sum(v for k,v in grams.items() if k.startswith('Support'))
    r=json.loads((M/'bambu_slice_result.json').read_text());total=sum(f['total_used_g'] for p in r['sliced_plates'] for f in p['filaments'])
    assert abs(sum(grams.values())-total)<.005,('feature mass accounting',sum(grams.values()),total)
    result={'total_g':total,'support_g':support,'support_percent':100*support/total,'feature_g':grams,'support_interface_print_height_mm':sorted(interfaces),'feature_mass_sum_g':sum(grams.values()),'support_xyz_bounds_mm':[[min(p[i] for p in bounds) for i in range(3)],[max(p[i] for p in bounds) for i in range(3)]] if bounds else None,'settings':{k:settings.get(k) for k in ['printer_model','layer_height','nozzle_diameter','filament_type','enable_support','support_type','support_style','support_on_build_plate_only','support_threshold_angle','wall_loops','sparse_infill_density']},'process_default_differences':differences,'sha256':invocation}
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    import numpy as np
    sys.path.insert(0,str(H));import build as B
    verification=json.loads((M/'verification.json').read_text())
    names=list(verification['print_parts']);boxes={n:np.array(verification['print_parts'][n]['print_bounds_mm']) for n in names}
    def owner(p):
        # Each extrusion belongs to the part whose plate footprint (+6 mm for
        # leaning tree branches) contains it; footprints are 12 mm apart.
        for n in names:
            b=boxes[n]
            if b[0,0]-6<=p[0]<=b[1,0]+6 and b[0,1]-6<=p[1]<=b[1,1]+6:return n
        return 'unassigned'
    def to_assembly(name,p):
        tf=verification['print_transforms'][name]
        return (np.asarray(p)-np.array(tf['translation']))@np.array(tf['rotation'])
    def category(name,mid):
        # Accepted by Hsinlung: tray bottom-edge ring, cover top-edge ring,
        # underside of the lower cane-mouth top (including its rise to the module face).
        x,y,_=to_assembly(name,mid);h=mid[2]
        w,bot,top,rb,rt=B.section_params(float(x))
        if name=='Tray' and h<=2.2 and abs(y)>=w/2-rb-1:return 'accepted: tray bottom-edge ring'
        if name=='Front_cover' and x<.5:return 'accepted: under cane-mouth top'
        if name in ['Front_cover','Rear_cover'] and h<=1.2 and abs(y)>=w/2-rt-1:return 'accepted: cover top-edge ring'
        return 'NOT accepted'
    result['parts']={n:{'total_g':0.,'support_g':0.,'support_by_category_g':defaultdict(float),'not_accepted_assembly_bounds_mm':None} for n in names+['unassigned']}
    for yy,e,p in part_extrusions:result['parts'][owner(p)]['total_g']+=e*factor
    unaccepted=defaultdict(list)
    for seg,w in zip(support_segments,support_weights):
        mid=np.mean(seg,axis=0);n=owner(mid);c=category(n,mid) if n!='unassigned' else 'NOT accepted'
        result['parts'][n]['support_g']+=w*factor;result['parts'][n]['support_by_category_g'][c]+=w*factor
        if c=='NOT accepted':unaccepted[n].append(to_assembly(n,mid) if n!='unassigned' else mid)
    for n,pts in unaccepted.items():
        q=np.array(pts);result['parts'][n]['not_accepted_assembly_bounds_mm']=[q.min(0).tolist(),q.max(0).tolist()]
    for n,d in result['parts'].items():
        d['support_by_category_g']=dict(d['support_by_category_g'])
        d['support_percent']=100*d['support_g']/d['total_g'] if d['total_g'] else 0.
    if not result['parts']['unassigned']['total_g'] and not result['parts']['unassigned']['support_g']:del result['parts']['unassigned']
    cats=defaultdict(float)
    for d in result['parts'].values():
        for c,g in d['support_by_category_g'].items():cats[c]+=g
    result['support_by_category_g']=dict(cats)
    assert abs(sum(v['support_g'] for v in result['parts'].values())-support)<.001
    fig,axes=plt.subplots(len(names),1,figsize=(14,3.2*len(names)),dpi=150)
    for ax,name in zip(axes,names):
        bbox=boxes[name];horizontal=1 if name in B.TENONS else 0
        for segments,color,lw in [(object_segments,'#8c9da4',.18),(support_segments,'#e77f16',.45)]:
            a=np.array([v for v in segments if owner(np.mean(v,axis=0))==name])
            if len(a):ax.add_collection(LineCollection(a[:,:,[horizontal,2]],colors=color,linewidths=lw,rasterized=True))
        d=result['parts'][name]
        ax.set(xlim=(bbox[0,horizontal]-5,bbox[1,horizontal]+5),ylim=(-2,max(10,bbox[1,2]+3)),xlabel=('Print Y / mm' if horizontal else 'Print X / mm (long axis)'),ylabel='Print height / mm',
               title=f"{name}: support {d['support_g']:.3f} g | not accepted {d['support_by_category_g'].get('NOT accepted',0):.3f} g")
        ax.set_aspect('equal');ax.grid(alpha=.15)
    fig.suptitle(f'Actual Bambu G-code | orange = automatic support | {support:.2f} g ({100*support/total:.2f}%)')
    fig.tight_layout();fig.savefig(H/'renders/13_bambu_support.png');plt.close(fig)
    (M/'slice_verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2));return result
def publish():
    """Publish the audited native archive, then remove intermediate duplicates."""
    native=M/'Handle_H2C_Sliced.3mf'
    target=H/'Handle_Print_H2C.3mf'
    invocation=json.loads((M/'slice_command.json').read_text())
    if native.exists():
        assert hashlib.sha256(native.read_bytes()).hexdigest()==invocation['output_sha256']
        native.replace(target)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==invocation['output_sha256']
    (M/'Handle_Print_Input.3mf').unlink(missing_ok=True)

if __name__=='__main__':
    if '--audit-only' not in sys.argv:run()
    audit()
    publish()

