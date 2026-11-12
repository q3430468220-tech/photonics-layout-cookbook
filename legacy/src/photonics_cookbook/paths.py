"""Where generated files go.

Lumerical solvers can fail on non-ASCII paths (e.g. a folder named in Chinese),
so the build folder can be moved anywhere with the ``PHOTONICS_BUILD_DIR`` environment
variable, e.g. ``set PHOTONICS_BUILD_DIR=D:\\photonics_build`` on Windows.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_dir(*parts: str) -> Path:
    base = Path(os.environ.get("PHOTONICS_BUILD_DIR") or REPO_ROOT / "build")
    path = base.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    if not str(path.resolve()).isascii():
        warnings.warn(
            f"build folder {path} is not an ASCII path -- Lumerical may fail to write its data "
            "files there. Set PHOTONICS_BUILD_DIR, e.g. D:\\photonics_build.",
            stacklevel=2,
        )
    return path
