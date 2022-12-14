#!/usr/bin/env python3
# -*- mode: python -*-

import os
from pathlib import Path
import sys

from pbench.common.exceptions import BadConfig
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.database import init_db
from pbench.server.unpack_tarballs import UnpackTarballs

_NAME_ = "pbench-unpack-tarballs"

# The link source for the operation of this script.
_linksrc = "TO-UNPACK"


def main(cfg_name):
    if not cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG env variable.",
            file=sys.stderr,
        )
        return 2

    try:
        config = PbenchServerConfig(cfg_name)
    except BadConfig as e:
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 1

    BUCKET = str(sys.argv[1]) if len(sys.argv) > 1 else None
    prog = Path(sys.argv[0]).name

    lowerbound, upperbound = 0.0, float("inf")

    if BUCKET:
        lowerbound = config.get(
            f"pbench-unpack-tarballs/{BUCKET}", "lowerbound", fallback=lowerbound
        )
        lowerbound = float(lowerbound) * 1024.0 * 1024.0

        upperbound = config.get(
            f"pbench-unpack-tarballs/{BUCKET}", "upperbound", fallback=upperbound
        )
        upperbound = float(upperbound) * 1024.0 * 1024.0
        prog = f"{prog}-{BUCKET}"

    logger = get_pbench_logger(prog, config)

    # We're going to need the Postgres DB to track dataset state, so setup
    # DB access.
    init_db(config, logger)

    # Initiate the unpacking
    unpack_obj = UnpackTarballs(config, logger)
    result = unpack_obj.unpack_tarballs(lowerbound, upperbound)

    result_string = (
        f"Total processed: {result.total},"
        f" Total successes: {result.success},"
        f" Total failures: {result.total - result.success}"
    )

    logger.info(result_string)

    # prepare and send report
    unpack_obj.report(prog, result_string)

    logger.info("end-{}", config.TS)

    return 0


if __name__ == "__main__":
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    status = main(cfg_name)
    sys.exit(status)
