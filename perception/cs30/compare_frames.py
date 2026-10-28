#!/usr/bin/env python3
"""比较两帧 CS30 原始深度（640×480 uint16 小端毫米），用于真机验收第 1、2 条。

    python perception/cs30/compare_frames.py 手机存的帧.bin 电脑上SDK或independent_proof存的帧.raw

输出两帧的 SHA-256、各自有效像素数，以及两帧都有效（> 10 mm，与 REPORT 相同）的像素上的差值统计。
同一次曝光时应逐字节相同（SHA-256 一致）；先后两次曝光、相机和场景都不动时，
REPORT 的参考值是差值中位数约 3 mm、P95 约 12 mm。
"""

import hashlib
import sys

import numpy as np


def load(path):
    raw = open(path, "rb").read()
    if len(raw) != 640 * 480 * 2:
        sys.exit(f"{path}：大小 {len(raw)} 字节，应为 614400")
    return raw, np.frombuffer(raw, dtype="<u2").reshape(480, 640).astype(np.int32)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    (ra, a), (rb, b) = load(sys.argv[1]), load(sys.argv[2])
    print("SHA-256 A", hashlib.sha256(ra).hexdigest())
    print("SHA-256 B", hashlib.sha256(rb).hexdigest())
    print("逐字节相同" if ra == rb else "不完全相同")
    va, vb = a > 10, b > 10
    both = va & vb
    print(f"有效像素 A {int(va.sum())}，B {int(vb.sum())}，两边都有效 {int(both.sum())}，"
          f"只在一边有效 {int((va ^ vb).sum())}")
    if both.any():
        d = np.abs(a[both] - b[both])
        print(f"两边都有效处 |A-B|：中位数 {np.median(d):.1f} mm，P95 {np.percentile(d, 95):.1f} mm，最大 {d.max()} mm")


if __name__ == "__main__":
    main()
