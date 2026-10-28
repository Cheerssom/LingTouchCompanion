"""Disposable CS30 protocol proof. Generic libusb; no manufacturer DLLs."""
import sys,pathlib,ctypes as C,time,json,collections,struct,traceback
root=pathlib.Path(__file__).parent;sys.path.insert(0,str(root/'packages'))
import usb.core,usb.util,usb.backend.libusb1 as u,libusb_package
out=root/'independent_runs'/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True)
backend=libusb_package.get_libusb1_backend();lib=u._lib
class Timeval(C.Structure):
 _fields_=[('tv_sec',C.c_long),('tv_usec',C.c_long)]
lib.libusb_handle_events_timeout.argtypes=[C.c_void_p,C.POINTER(Timeval)]
lib.libusb_handle_events_timeout.restype=C.c_int
sequence=json.loads((root/'startup_sequence.json').read_text())
def modules():
 k=C.WinDLL('kernel32',use_last_error=True);mods=(C.c_void_p*2048)();needed=C.c_ulong()
 k.GetCurrentProcess.restype=C.c_void_p;proc=k.GetCurrentProcess()
 k.K32EnumProcessModules.argtypes=[C.c_void_p,C.c_void_p,C.c_ulong,C.c_void_p]
 k.K32GetModuleFileNameExW.argtypes=[C.c_void_p,C.c_void_p,C.c_wchar_p,C.c_ulong]
 k.K32EnumProcessModules(proc,mods,C.sizeof(mods),C.byref(needed));paths=[]
 for m in mods[:needed.value//C.sizeof(C.c_void_p)]:
  s=C.create_unicode_buffer(32768);k.K32GetModuleFileNameExW(proc,m,s,len(s));paths.append(s.value)
 assert not any(x.lower().endswith(('synexenssdk.dll','csreconstruction2.0.dll','sonixcamera.dll')) for x in paths)
 return paths
class Capture:
 def __init__(self,cycle):
  self.path=out/f'cycle_{cycle}';self.path.mkdir();self.events=open(self.path/'events.jsonl','w')
  self.d=usb.core.find(idVendor=0x2207,idProduct=0x16,backend=backend)
  if self.d is None:raise RuntimeError('CS30 absent')
  self.allocs=[];self.buffers=[];self.frames=[];self.times=[];self.parts=[];self.fid=None
  self.errs=collections.Counter();self.running=False;self.pending=set()
  self.cb=u._libusb_transfer_cb_fn_p(self.callback)
 def log(self,kind,**kw):
  v={'kind':kind,'time':time.perf_counter(),**kw};self.events.write(json.dumps(v)+'\n');self.events.flush()
  if kind!='frame':print(v,flush=True)
 def finish(self):
  b=b''.join(self.parts)
  if len(b)==614400:self.frames.append(b);self.times.append(time.perf_counter());self.log('frame',i=len(self.frames)-1,length=len(b))
  elif b:self.errs['incomplete_'+str(len(b))]+=1
 def packet(self,b):
  if len(b)<2:return
  h=b[0];f=b[1]
  if not 2<=h<=len(b):self.errs['bad_header']+=1;return
  if self.fid is not None and self.fid!=(f&1) and self.parts:self.finish();self.parts=[]
  self.fid=f&1
  if f&0x40:self.errs['uvc_error']+=1;self.parts=[];return
  self.parts.append(b[h:])
  if f&2:self.finish();self.parts=[]
 def callback(self,t):
  self.pending.discard(C.addressof(t.contents))
  try:
   v=t.contents
   if v.status==0:
    offset=0
    for desc in u._get_iso_packet_list(v):
     if desc.status==0 and desc.actual_length:self.packet(C.string_at(v.buffer+offset,desc.actual_length))
     elif desc.status:self.errs['packet_'+str(desc.status)]+=1
     offset+=desc.length
   elif v.status!=3:self.errs['transfer_'+str(v.status)]+=1
   if self.running:
    r=lib.libusb_submit_transfer(t)
    if r:self.errs['resubmit_'+str(r)]+=1
    else:self.pending.add(C.addressof(t.contents))
  except Exception as e:self.log('callback_error',error=str(e))
 def queue(self):
  self.running=True;handle=self.d._ctx.handle.handle
  for i in range(10):
   t=lib.libusb_alloc_transfer(32);buf=(C.c_ubyte*98304)();self.buffers.append(buf);self.allocs.append(t)
   lib.libusb_fill_iso_transfer(t,handle,0x82,C.cast(buf,C.POINTER(C.c_ubyte)),len(buf),32,self.cb,None,5000)
   lib.libusb_set_iso_packet_lengths(t,3072);r=lib.libusb_submit_transfer(t)
   if r:raise RuntimeError(('submit',r))
   self.pending.add(C.addressof(t.contents))
  self.log('queue_iso',transfers=10,packets=32,packet_bytes=3072,endpoint=130)
 def events_for(self,seconds):
  end=time.perf_counter()+seconds
  while time.perf_counter()<end:
   r=lib.libusb_handle_events_timeout(backend.ctx,C.byref(Timeval(0,10000)))
   if r:raise RuntimeError(('events',r))
 def start(self):
  for step in sequence:
   if step['kind']=='alt':
    i,a=step['interface'],step['alt'];usb.util.claim_interface(self.d,i)
    self.log('alt_submit',interface=i,alt=a);self.d.set_interface_altsetting(interface=i,alternate_setting=a);self.log('alt_complete',interface=i,alt=a)
   elif step['kind']=='queue_iso':self.queue()
   elif step['kind']=='control':
    rt,req,val,idx,n=struct.unpack('<BBHHH',bytes(step['setup']));data=n if rt&128 else bytes(step['data'])
    self.log('control_submit',setup=step['setup'],data=bytes(data).hex() if not isinstance(data,int) else data)
    t=time.perf_counter();r=self.d.ctrl_transfer(rt,req,val,idx,data,timeout=15000)
    self.log('control_complete',setup=step['setup'],elapsed_ms=(time.perf_counter()-t)*1000,result=bytes(r).hex() if rt&128 else int(r))
    if val==0xa700 and not rt&128:self.events_for(.270)
  self.log('started')
 def close(self):
  self.running=False
  for t in self.allocs:
   if C.addressof(t.contents) in self.pending:lib.libusb_cancel_transfer(t)
  end=time.perf_counter()+3
  while self.pending and time.perf_counter()<end:self.events_for(.01)
  if self.pending:self.log('pending_at_close',count=len(self.pending))
  for i in [1,0]:
   try:self.d.set_interface_altsetting(interface=i,alternate_setting=0);self.log('stop_alt',interface=i,alt=0)
   except Exception as e:self.log('stop_error',interface=i,error=str(e))
  for t in self.allocs:
   if C.addressof(t.contents) not in self.pending:lib.libusb_free_transfer(t)
  usb.util.dispose_resources(self.d);self.log('closed')
 def save(self):
  for i,b in enumerate(self.frames):(self.path/f'depth_{i:03}.raw').write_bytes(b)
  s={'frames':len(self.frames),'frame_bytes':614400,'fps':(len(self.times)-1)/(self.times[-1]-self.times[0]) if len(self.times)>1 else 0,'times':self.times,'errors':dict(self.errs),'vendor_dlls_loaded':False}
  (self.path/'result.json').write_text(json.dumps(s,indent=2));return s
def recover():
 result=[];d=usb.core.find(idVendor=0x2207,idProduct=0x16,backend=backend)
 if d is None:return ['Device absent']
 try:
  usb.util.dispose_resources(d);result.append('Released interfaces and reopened')
  try:result.append('descriptor after reopen: '+d.product);return result
  except Exception as e:result.append('reopen descriptor failed: '+str(e))
  try:d.reset();result.append('libusb_reset_device succeeded')
  except Exception as e:result.append('libusb_reset_device failed: '+str(e))
 finally:usb.util.dispose_resources(d)
 time.sleep(2)
 try:d=usb.core.find(idVendor=0x2207,idProduct=0x16,backend=backend);result.append('descriptor after reset: '+d.product)
 except Exception as e:result.append('descriptor after reset failed: '+str(e))
 return result
results=[]
try:
 for cycle in range(2):
  cap=Capture(cycle)
  try:cap.start();cap.events_for(6)
  finally:cap.close();results.append(cap.save());cap.events.close()
  if not cap.frames:raise RuntimeError('No complete depth frames')
  time.sleep(.25)
 (out/'modules.txt').write_text('\n'.join(modules()));(out/'results.json').write_text(json.dumps(results,indent=2))
 print('SUCCESS',out,[(x['frames'],x['fps']) for x in results],flush=True)
except Exception:
 traceback.print_exc();r=recover();(out/'recovery.json').write_text(json.dumps(r,indent=2));print('FAILED',out,r,flush=True);sys.exit(1)
