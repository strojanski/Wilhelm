"""Entry point for the TEE extension server."""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base.server import Server
from base.signer import Signer
from app.config import VERSION
from app.handlers import register, report_state


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    ext_port  = os.environ.get("EXTENSION_PORT", "8080")
    sign_port = os.environ.get("SIGN_PORT", "9090")

    signer = Signer()
    signer.start_http(sign_port)

    srv = Server(ext_port, sign_port, VERSION, register, report_state, signer=signer)
    srv.listen_and_serve()


if __name__ == "__main__":
    main()
