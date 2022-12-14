#!/usr/bin/env python3
# -*- mode: python -*-

from argparse import ArgumentParser
import os
from pathlib import Path
import sys

from pbench.common.exceptions import BadConfig

# Export all the expected pbench config file attributes for the
# existing shell scripts.  This maintains the single-source-of-
# truth for those definitions in the PbenchServerConfig class, but
# still accessible to all pbench bash shell scripts.
from pbench.server import PbenchServerConfig

if __name__ != "__main__":
    sys.exit(1)

_NAME_ = "pbench-base.py"

parser = ArgumentParser(_NAME_)
parser.add_argument("-C", "--config", dest="cfg_name", help="Specify config file")
parser.set_defaults(cfg_name=os.environ.get("_PBENCH_SERVER_CONFIG"))
parser.add_argument(
    "prog", metavar="PROG", type=str, nargs=1, help="the program name of the caller"
)
parser.add_argument(
    "args", metavar="args", type=str, nargs="*", help="program arguments"
)
parsed, _ = parser.parse_known_args()

prog_path = Path(parsed.prog[0])
_prog = prog_path.name
_dir = prog_path.parent

if not parsed.cfg_name:
    # pbench-base.py is not always invoked with -C or --config or the _PBENCH_SERVER_CONFIG
    # environment variable set.  Since we really need access to the config
    # file to operate, and we know the relative location of that config file,
    # we check to see if that exists before declaring a problem.
    config_path = Path(_dir.parent, "lib", "config", "pbench-server.cfg")
    if not config_path.exists():
        print(
            f"{_prog}: No config file specified: set _PBENCH_SERVER_CONFIG env variable or use"
            f" --config <file> on the command line",
            file=sys.stderr,
        )
        sys.exit(1)
else:
    config_path = Path(parsed.cfg_name)

try:
    config = PbenchServerConfig(config_path)
except BadConfig as e:
    print(f"{_prog}: {e} (config file {config_path})", file=sys.stderr)
    sys.exit(1)

# Exclude the "files" and "conf" attributes from being exported
vars = sorted(
    [
        key
        for key in config.__dict__.keys()
        if key
        not in ("files", "conf", "timestamp", "_unittests", "_ref_datetime", "get")
    ]
)
for att in vars:
    try:
        os.environ[att] = str(getattr(config, att))
    except AttributeError:
        print(
            f'{_prog}: Missing internal pbench attribute, "{att}", in configuration',
            file=sys.stderr,
        )
        sys.exit(1)

if config._unittests:
    os.environ["_PBENCH_SERVER_TEST"] = "1"

cmd = f"{sys.argv[1]}.sh"
args = [cmd] + sys.argv[2:]
os.execv(cmd, args)
