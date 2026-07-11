import hashlib
import json
from typing import Any


def compute_checksum(attributes: dict[str, Any]) -> str:
    canonical = json.dumps(attributes, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
