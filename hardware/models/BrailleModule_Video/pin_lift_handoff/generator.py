"""Raised look for every pin, generated from that pin's OWN pixels in the all-down plate.

frame(H) -> full picture, H = (10,9) array of pin heights in mm (0 = down).

How one pin is drawn at height h:
  1. hole plate  : the pin's old place is filled with the hole's own dark colour (what shows once the pin has moved)
  2. pin texture : the pin's lit pixels; shadowed / hidden parts and a ring beyond the rim are continued from them
  3. placement   : the middle of the head slides rigidly by h * (image shift per mm, from the fitted camera) - no scaling, the
                   highlight rides along; towards the rim the texture is eased outwards so the head reaches the full pin diameter
  4. light       : brightened linearly with height up to HOLD
  5. shaft       : only above CAP mm, a slightly darker band under the head
Numbers marked TUNED are visual settings, not measurements."""
import os, numpy as np, cv2, config
BASE=cv2.imread(config.BASE_IMG).astype(np.float32); REF=cv2.imread(config.REF_IMG).astype(np.float32)
cam=np.load(os.path.join(config.WORK,'cam.npz')); grid=np.load(os.path.join(config.WORK,'grid.npy'))
f=float(cam['f']); rvec=cam['rvec']; tvec=cam['tvec']; Xw=cam['Xw']; sgn=float(cam['sgn']); pp=cam['pp']
K=np.array([[f,0,pp[0]],[0,f,pp[1]],[0,0,1.]])
def proj(X):
    uv,_=cv2.projectPoints(np.asarray(X,np.float64).reshape(-1,3),rvec,tvec,K,None); return uv.reshape(-1,2)
def local(r,c):
    X0=Xw[(r//2)*3+(c//3),(r%2)*3+(c%3)].copy(); p0=proj(X0)[0]
    e=0.2; J=np.stack([(proj(X0+[e,0,0])[0]-p0)/e,(proj(X0+[0,e,0])[0]-p0)/e],1)      # px per mm in the surface plane
    sig=proj(X0+[0,0,sgn*1.0])[0]-p0                                                   # px per mm of rise
    return J,sig
# pin shape: radius 0.71 and cap height 0.45 mm are the repo's parameters.json values (estimated from the drawing, not measured).
# D0 = how far down the cap is still lit when the pin is down; TUNED on the centre module so the lit disc comes out ~1.28 mm wide.
A_PIN=0.71; CAP=0.45; RS=(A_PIN**2+CAP**2)/(2*CAP); D0=0.33
rad=lambda d: float(np.sqrt(max(2*RS*d-d*d,1e-6)))
RVIS=rad(D0)
WIN=38; S=2*WIN+1          # per-pin work window, px. All px constants in this file assume ~23 px/mm (1086x1448 plate)
YY,XX=np.mgrid[0:S,0:S].astype(np.float32)
def prep(r,c):
    cx,cy=grid[r,c,0],grid[r,c,1]; x0=int(round(cx))-WIN; y0=int(round(cy))-WIN
    src=BASE[y0:y0+S,x0:x0+S].copy(); g=cv2.GaussianBlur(src.mean(2),(0,0),0.5)
    J,sig=local(r,c); Ji=np.linalg.inv(J); px=float(np.sqrt(abs(np.linalg.det(J))))*RVIS   # mean radius in px
    def rho(ox,oy,k=1.0):
        dx=XX-ox; dy=YY-oy
        return np.sqrt((Ji[0,0]*dx+Ji[0,1]*dy)**2+(Ji[1,0]*dx+Ji[1,1]*dy)**2)/(RVIS*k)
    m=(g>80).astype(np.uint8); n,lab=cv2.connectedComponents(m,connectivity=8); m=(lab==lab[WIN,WIN]).astype(np.uint8)
    cnt=max(cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)[0],key=len).reshape(-1,2).astype(np.float32)
    mc=np.array([XX[m>0].mean(),YY[m>0].mean()])
    # keep only outline points that are a real edge of the pin (pitch dark just outside), drop shadow / hidden edges
    d=cnt-mc; d/=np.linalg.norm(d,axis=1,keepdims=True)+1e-6; q=cnt+2.5*d
    outside=cv2.remap(g,q[:,0].reshape(-1,1).astype(np.float32),q[:,1].reshape(-1,1).astype(np.float32),cv2.INTER_LINEAR).ravel()
    limb=cnt[outside<42]
    if len(limb)<12: limb=cnt
    best=(1e9,mc)
    for oy in np.arange(mc[1]-6,mc[1]+6.01,0.25):
        for ox in np.arange(mc[0]-6,mc[0]+6.01,0.25):
            dx=limb[:,0]-ox; dy=limb[:,1]-oy
            rr=np.sqrt((Ji[0,0]*dx+Ji[0,1]*dy)**2+(Ji[1,0]*dx+Ji[1,1]*dy)**2)/RVIS
            e=np.mean((rr-1)**2)
            if e<best[0]: best=(e,(ox,oy))
    ex,ey=best[1]; r0=rho(ex,ey)
    inner=(r0<0.75)&(m>0); med=np.median(g[inner]) if inner.sum()>20 else 125.
    # texture: the pin's own pixels where they are lit, everything else (shadowed side, hidden part, beyond the rim) continued from them
    el5=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5))
    bad_dark=cv2.dilate(((g<0.86*med)&(r0>0.45)&(r0<1.7)).astype(np.uint8),el5)
    bad=(bad_dark>0)|((r0>1-2.0/px)&(r0<1.7))
    hl=cv2.dilate(((g>med+22)&(r0<1.0)).astype(np.uint8),el5)>0          # specular highlight: keep it, but never let it bleed outwards
    u=np.clip(src,0,255).astype(np.uint8)
    nohl=cv2.inpaint(u,(hl|bad).astype(np.uint8),5,cv2.INPAINT_TELEA)       # diffuse colour only
    fill=nohl.astype(np.float32)
    good=cv2.erode((~bad).astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))).astype(np.float32)
    keep=np.minimum(cv2.GaussianBlur(good,(0,0),1.0),(~bad).astype(np.float32))[...,None]
    tex=src*keep+fill*(1-keep)
    # empty-hole plate
    ring=(r0>1.12)&(r0<1.55)&(g<24)
    dark=np.median(src[ring],axis=0) if ring.sum()>15 else np.array([14,12,10],np.float32)
    rng=np.random.default_rng(1000+r*9+c)
    om=np.maximum(np.clip(0.5-(r0-1.10)*px/1.4,0,1),cv2.GaussianBlur(cv2.dilate(m,np.ones((3,3),np.uint8)).astype(np.float32),(0,0),0.7)*np.clip(0.5-(r0-1.24)*px/1.4,0,1))[...,None]
    hole=src*(1-om)+(dark+rng.normal(0,1.2,(S,S,1)).astype(np.float32))*om
    # what makes this pin different from its neighbours when raised. Fixed per pin (seeded), all ranges TUNED by eye:
    # height factor, sideways offset px, size, brightness, outline wobble, a little extra showing on the camera side
    vr=np.random.default_rng(5000+r*9+c)
    var=dict(hf=float(np.clip(vr.normal(1,0.10),0.8,1.2)), off=(float(vr.normal(0,0.6)),float(vr.normal(0,0.45))),
             size=float(np.clip(vr.normal(1,0.02),0.96,1.04)), gain=float(np.clip(vr.normal(1,0.025),0.94,1.06)),
             harm=[(2,float(vr.normal(0,0.012)),float(vr.uniform(0,6.28))),(3,float(vr.normal(0,0.010)),float(vr.uniform(0,6.28)))],
             lobe_amp=float(vr.uniform(0,1.3)), lobe_ang=float(vr.normal(0,0.5)), lobe_w=float(vr.uniform(0.5,0.9)))
    return dict(x0=x0,y0=y0,src=src,tex=tex,hole=hole,om=om[...,0],rho=rho,e=(float(ex),float(ey)),px=px,sig=sig,fit=best[0],nl=len(limb),var=var)
PRE={(r,c):prep(r,c) for r in range(10) for c in range(9)}
# HOLD: resting raised height, mm (TUNED; drawing says 0.4-0.5). GAIN: how much brighter a raised head is, taken from the four raised
# pins in the reference picture (1.19-1.28). RHO0: inside this share of the radius the head moves rigidly. RIM, SIDE: TUNED.
HOLD=0.5; GAIN=1.24; RHO0=0.5; RIM=0.06; SIDE=0.975
VARY=True                    # False = every pin gets identical settings (the earlier, too-uniform look)
NOVAR=dict(hf=1.0,off=(0.0,0.0),size=1.0,gain=1.0,harm=[],lobe_amp=0.0,lobe_ang=0.0,lobe_w=0.7)
def pin_patch(P,h):
    sig=P['sig']; ex,ey=P['e']; V=P['var'] if VARY else NOVAR
    lit=min(1.0,h/HOLD)
    d=min(CAP,D0+h); k=rad(d)/RVIS*(1+(V['size']-1)*lit); zc=h-d+D0
    fx,fy=V['off'][0]*lit,V['off'][1]*lit                      # sideways play of the pin in its hole
    ox,oy=zc*sig[0]+fx,zc*sig[1]+fy
    rn=P['rho'](ex+ox,ey+oy,k); pxn=P['px']*k
    if V['harm'] or V['lobe_amp']>0:                           # outline is not a perfect ellipse, and not the same on every pin
        th=np.arctan2(YY-(ey+oy),XX-(ex+ox)); pert=np.zeros_like(rn)
        for m,a_,ph in V['harm']: pert+=a_*np.cos(m*th+ph)
        near=np.arctan2(-sig[1],-sig[0])+V['lobe_ang']
        dang=np.angle(np.exp(1j*(th-near)))
        pert+=(V['lobe_amp']/pxn)*np.exp(-(dang/V['lobe_w'])**2)
        rn=rn/(1+pert*lit)
    w=np.clip((rn-RHO0)/(1-RHO0),0,1); w=w*w*(3-2*w)
    ycx=XX-(h*sig[0]+fx); ycy=YY-(h*sig[1]+fy)
    yex=ex+(XX-(ex+ox))/k; yey=ey+(YY-(ey+oy))/k
    mx=(ycx+w*(yex-ycx)).astype(np.float32); my=(ycy+w*(yey-ycy)).astype(np.float32)
    rgb=cv2.remap(P['tex'],mx,my,cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
    rim=1+RIM*lit*(1-min(1.0,max(0.0,h-CAP)/0.08))*np.exp(-(((1-rn)*pxn-0.9)/0.8)**2)
    rgb=np.clip(rgb*(1+(GAIN*V['gain']-1)*lit)*rim[...,None],0,255)
    alpha=np.clip(0.5-(rn-1)*pxn/1.4,0,1)
    return rgb,alpha
def render(Hmm):
    out=BASE.copy()
    for r in range(10):
        for c in range(9):
            h=float(Hmm[r,c])
            if h<=1e-4: continue
            P=PRE[(r,c)]; x0,y0=P['x0'],P['y0']
            rgb,al=pin_patch(P,h); dst=P['hole'].copy(); touched=np.maximum(P['om'],al)
            ex_side=h-CAP
            if ex_side>0.01:
                sig=P['sig']; n=max(1,int(np.ceil(ex_side*np.hypot(*sig)*2)))
                side=cv2.GaussianBlur(rgb,(0,0),2.0)*SIDE
                for j in range(n,0,-1):
                    t=ex_side*j/n; M=np.float32([[1,0,-t*sig[0]],[0,1,-t*sig[1]]])
                    a_s=cv2.warpAffine(al,M,(S,S),flags=cv2.INTER_LINEAR,borderValue=0)
                    p_s=cv2.warpAffine(side,M,(S,S),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
                    dst=dst*(1-a_s[...,None])+p_s*a_s[...,None]; touched=np.maximum(touched,a_s)
            new=dst*(1-al[...,None])+rgb*al[...,None]
            wm=(cv2.dilate((touched>0).astype(np.uint8),np.ones((3,3),np.uint8))>0)      # only this dot's own pixels are written
            win=out[y0:y0+S,x0:x0+S]; win[wm]=new[wm]
    return out
def u8(I): return np.clip(I,0,255).astype(np.uint8)

_cache={}
def dot_layer(r,c,h):
    """(window pixels, write-mask) for one dot at height h; cached"""
    key=(r,c,round(float(h),3))
    if key not in _cache:
        H=np.zeros((10,9)); H[r,c]=h
        P=PRE[(r,c)]; x0,y0=P['x0'],P['y0']
        full=render(H); win=full[y0:y0+S,x0:x0+S].copy()
        wm=np.abs(win-BASE[y0:y0+S,x0:x0+S]).max(2)>0
        _cache[key]=(win,wm)
    return _cache[key]
def frame(Hmm):
    out=BASE.copy()
    for r in range(10):
        for c in range(9):
            if Hmm[r,c]>1e-4:
                P=PRE[(r,c)]; win,wm=dot_layer(r,c,Hmm[r,c]); o=out[P['y0']:P['y0']+S,P['x0']:P['x0']+S]; o[wm]=win[wm]
    return out
