"""Locate Ansys Lumerical and import its Python API (lumapi).

lumapi is shipped with Lumerical, not on PyPI.  Every script in this repository gets it from here:

    from lumerical_env import import_lumapi, lumerical_root
    lumapi = import_lumapi()

The installation is found in this order:
    1. the environment variable LUMERICAL_ROOT  (the folder that contains ``api/python/lumapi.py``),
       e.g.  C:/Program Files/ANSYS Inc/v251/Lumerical   or   /opt/lumerical/v251
    2. the usual install locations on every drive (Windows) or under /opt (Linux); the newest wins.
"""

from __future__ import annotations

import os
import string
import sys
from pathlib import Path


def _candidates() -> list[Path]:
    found: list[Path] = []
    if sys.platform == "win32":
        for drive in string.ascii_uppercase:
            base = Path(f"{drive}:/Program Files")
            if not base.exists():
                continue
            found += base.glob("ANSYS Inc/v*/Lumerical")
            found += base.glob("Ansys Inc/v*/Lumerical")
            found += base.glob("Lumerical/v*")
    else:
        found += Path("/opt/lumerical").glob("v*")
        found += Path("/opt/ansys_inc").glob("v*/Lumerical")
    return sorted((p for p in found if (p / "api" / "python" / "lumapi.py").exists()), reverse=True)


def lumerical_root() -> Path:
    """Folder of the Lumerical installation (contains ``api/python`` and ``bin``)."""
    env = os.environ.get("LUMERICAL_ROOT")
    if env:
        root = Path(env)
        if not (root / "api" / "python" / "lumapi.py").exists():
            raise SystemExit(f"LUMERICAL_ROOT={env} does not contain api/python/lumapi.py")
        return root
    found = _candidates()
    if not found:
        raise SystemExit(
            "Ansys Lumerical was not found.  Set the environment variable LUMERICAL_ROOT to the folder "
            "that contains api/python/lumapi.py, e.g. C:/Program Files/ANSYS Inc/v251/Lumerical"
        )
    return found[0]


def import_lumapi():
    """Import and return the ``lumapi`` module of the located installation."""
    api = str(lumerical_root() / "api" / "python")
    if api not in sys.path:
        sys.path.append(api)
    import lumapi

    return lumapi


if __name__ == "__main__":
    print("Lumerical:", lumerical_root())
    print("lumapi   :", import_lumapi().__file__)
