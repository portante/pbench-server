#!/usr/bin/env python3

import os
import shutil
import sys

_prog = os.path.basename(sys.argv[0])

if len(sys.argv) < 2:
    print(f"{_prog}: Missing working directory argument", file=sys.stderr)
    sys.exit(1)

if len(sys.argv) > 2:
    print(f"{_prog}: Too many arguments ({sys.argv!r})", file=sys.stderr)
    sys.exit(1)

try:
    os.chdir(sys.argv[1])
except Exception as e:
    print(f"{_prog}: {e}", file=sys.stderr)
    sys.exit(1)

errors = 0
for tar in sys.stdin:
    try:
        src = tar.strip("\n")
        des = src.replace("TO-SYNC", "TO-DELETE")
        shutil.move(src, des)
    except Exception as e:
        errors += 1
        print(f"{_prog}: {e}", file=sys.stderr)
        continue

sys.exit(1 if errors > 0 else 0)
