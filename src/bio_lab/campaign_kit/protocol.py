"""Read registration/protocol.json and its constants block.

confirm.py reads every registered constant through load_constants(), so the
value in the code is the value in the registration by construction; the
protocol linter (lint.py) checks any literal that is left in the code.
"""

from __future__ import annotations

import os
from pathlib import Path

from .common import KitError, read_json

PROTOCOL = "registration/protocol.json"


def load_protocol(campaign_dir: os.PathLike | str) -> dict:
    return read_json(Path(campaign_dir) / PROTOCOL, "registration/protocol.json")


def load_constants(campaign_dir: os.PathLike | str) -> dict:
    """The protocol's "constants" object; a missing or empty block is an error."""
    constants = load_protocol(campaign_dir).get("constants")
    if not isinstance(constants, dict) or not constants:
        raise KitError("registration/protocol.json has no nonempty \"constants\" object")
    return dict(constants)


def constant(campaign_dir: os.PathLike | str, name: str):
    constants = load_constants(campaign_dir)
    if name not in constants:
        raise KitError(f"constant {name} is not registered in protocol.json")
    return constants[name]
