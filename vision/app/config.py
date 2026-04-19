"""Extension configuration constants."""

import os

VERSION = "0.1.0"

OP_TYPE_VISION     = "VISION"
OP_COMMAND_ANALYZE = "ANALYZE"
OP_COMMAND_HEALTH  = "HEALTH"

VISION_API_URL = os.environ.get("VISION_API_URL", "http://localhost:8000")
