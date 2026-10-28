"""Paths. Override with environment variables PIN_BASE / PIN_REF / PIN_VIDEO if the files live elsewhere."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
BASE_IMG   = os.environ.get('PIN_BASE',  os.path.join(HERE, 'inputs', '11_all_down.png'))      # every pin down: the plate everything is drawn on
REF_IMG    = os.environ.get('PIN_REF',   os.path.join(HERE, 'inputs', '10_reference.png'))     # same picture with four pins up: look reference only
REAL_VIDEO = os.environ.get('PIN_VIDEO', os.path.join(HERE, 'inputs', 'PhysicalMotionReference.mp4'))
WORK = os.path.join(HERE, 'work'); OUT = os.path.join(HERE, 'out')
os.makedirs(WORK, exist_ok=True); os.makedirs(OUT, exist_ok=True)
