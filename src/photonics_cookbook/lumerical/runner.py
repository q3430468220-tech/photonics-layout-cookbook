"""Run generated scripts through Lumerical's Python API (lumapi).

``lumapi`` ships with Lumerical (``<install>/api/python/lumapi.py``); it is not on
PyPI. :func:`import_lumapi` finds it from, in order:

1. the ``root`` argument,
2. the ``LUMERICAL_ROOT`` environment variable (folder that contains ``api/python``),
3. the usual install folders on Windows / Linux (newest version first).

Example (Windows, Lumerical 2025 R1)::

    set LUMERICAL_ROOT=D:\\Program Files\\ANSYS Inc\\v251\\Lumerical
    uv run python examples/01_devices/01_ring_modulator/03_run_lumerical.py
"""

from __future__ import annotations

import glob
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

PRODUCTS = {"fdtd": "FDTD", "mode": "MODE", "charge": "DEVICE", "device": "DEVICE", "interconnect": "INTERCONNECT"}

_SEARCH = [
    r"C:\Program Files\ANSYS Inc\v*\Lumerical",
    r"D:\Program Files\ANSYS Inc\v*\Lumerical",
    r"C:\Program Files\Lumerical\v*",
    r"D:\Program Files\Lumerical\v*",
    "/opt/lumerical/v*",
    "/opt/ansys_inc/v*/Lumerical",
    "/usr/ansys_inc/v*/Lumerical",
]


def candidate_roots(root: str | os.PathLike | None = None) -> list[Path]:
    roots: list[Path] = []
    if root:
        roots.append(Path(root))
    if os.environ.get("LUMERICAL_ROOT"):
        roots.append(Path(os.environ["LUMERICAL_ROOT"]))
    for pattern in _SEARCH:
        roots += [Path(p) for p in sorted(glob.glob(pattern), reverse=True)]
    return roots


def find_lumapi(root: str | os.PathLike | None = None) -> Path:
    """Folder containing ``lumapi.py``."""
    tried = []
    for r in candidate_roots(root):
        for sub in (r / "api" / "python", r):
            tried.append(str(sub))
            if (sub / "lumapi.py").exists():
                return sub
    raise FileNotFoundError(
        "lumapi.py not found. Set LUMERICAL_ROOT to your Lumerical folder, e.g. "
        r"'D:\Program Files\ANSYS Inc\v251\Lumerical'. Tried: " + "; ".join(tried[:8])
    )


def import_lumapi(root: str | os.PathLike | None = None) -> ModuleType:
    """Import and return the ``lumapi`` module."""
    if "lumapi" in sys.modules:
        return sys.modules["lumapi"]
    api = find_lumapi(root)
    sys.path.insert(0, str(api))
    if hasattr(os, "add_dll_directory"):  # Windows: interop DLLs live next to lumapi / in bin
        for d in (api, api.parent.parent / "bin"):
            if d.exists():
                os.add_dll_directory(str(d))
    return importlib.import_module("lumapi")


def run_script(
    product: str,
    script: str | os.PathLike,
    root: str | os.PathLike | None = None,
    hide: bool = False,
    keep_open: bool = False,
):
    """Open ``product`` (fdtd / mode / charge), ``cd`` to the script folder and run it.

    Returns the open session if ``keep_open`` (close it yourself), else ``None``.
    """
    lumapi = import_lumapi(root)
    cls = getattr(lumapi, PRODUCTS[product.lower()])
    script = Path(script).resolve()
    if not str(script).isascii():
        print(f"WARNING: non-ASCII path {script} -- Lumerical may fail to write its files.")
    sess = cls(hide=hide)
    try:
        sess.cd(str(script.parent))
        sess.feval(str(script))
    except Exception:
        if not keep_open:
            sess.close()
        raise
    if keep_open:
        return sess
    sess.close()
    return None
