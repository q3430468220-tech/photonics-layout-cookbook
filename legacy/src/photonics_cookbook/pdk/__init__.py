"""The cookbook's gdsfactory PDKs, generated from the process files.

Typical use::

    from photonics_cookbook.pdk import activate_pdk
    pdk = activate_pdk("cornerstone_si220_active")   # cspdk.si220 + implants, vias, metal
    c = gf.get_component("ring_modulator")
    xs = gf.get_cross_section("rib_pn")

or, exactly like a foundry PDK package::

    from photonics_cookbook.pdk.cornerstone_si220_active import PDK, LAYER
    PDK.activate()

How the PDK is put together is explained step by step in
``examples/00_getting_started/01_define_your_pdk.py`` and ``docs/pdk-tutorial.md``.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import gdsfactory as gf

from photonics_cookbook.pdk.builder import (
    DEFAULT_PROCESS,
    build_pdk,
    layer_map_from_process,
    layer_stack_from_process,
    layer_views_from_process,
    make_rib_pn,
    upstream_pdk,
)
from photonics_cookbook.process import Process

_CACHE: dict[str, gf.Pdk] = {}


def _key(process: str | Process) -> str:
    """Cache key: shipped processes by name, custom files by path."""
    from photonics_cookbook.process.model import _data_dir

    if isinstance(process, Process):
        src = Path(process.source)
        shipped = src.parent.resolve() == _data_dir().resolve()
        return src.stem if shipped else str(src.resolve())
    path = Path(str(process))
    return str(path.resolve()) if path.suffix else str(process)


def get_pdk(process: str | Process = DEFAULT_PROCESS) -> gf.Pdk:
    """Cookbook PDK for ``process`` (built once, then cached)."""
    key = _key(process)
    if key not in _CACHE:
        _CACHE[key] = build_pdk(process)
    return _CACHE[key]


def activate_pdk(process: str | Process = DEFAULT_PROCESS) -> gf.Pdk:
    """Build (if needed) and activate the cookbook PDK for ``process``. Returns it."""
    pdk = get_pdk(process)
    # force: a different PDK object with the same name (e.g. a customised copy of the
    # process file) must still replace the active one
    pdk.activate(force=True)
    return pdk


def active_pdk_or_none() -> gf.Pdk | None:
    """The active PDK, without gdsfactory's auto-activation of ``CONF.pdk``."""
    import gdsfactory.pdk as _pdk_module

    return getattr(_pdk_module, "_ACTIVE_PDK", None)


def ensure_pdk(process: str | Process = DEFAULT_PROCESS) -> gf.Pdk:
    """Activate the cookbook PDK only if *no* PDK is active yet (used inside cells).

    If you activated another PDK on purpose, it is left alone: cookbook cells draw
    with explicit (layer, datatype) numbers and still work.
    """
    active = active_pdk_or_none()
    return active if active is not None else activate_pdk(process)


def write_klayout_tech(process: str | Process = DEFAULT_PROCESS, out_dir: str | Path = "build/klayout_tech") -> Path:
    """Write KLayout technology files: ``layers.lyp``, ``tech.lyt`` and a 2.5D script.

    In KLayout: *File -> Load Layer Properties* with ``layers.lyp`` (colours and layer
    names), or *Tools -> Manage Technologies -> Import Technology* with ``tech.lyt``.
    ``d25/<name>.lyd25`` is a 2.5D view script (*Tools -> 2.5d View*), written
    by the cookbook because gdsfactory 9.5x leaves that step out.
    """
    pdk = get_pdk(process)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        pdk.klayout_technology.write_tech(tech_dir=out)
    except Exception as err:  # never lose the .lyp because of the technology file
        warnings.warn(f"KLayout technology export failed ({err}); writing layers.lyp only", stacklevel=2)
        pdk.get_layer_views().to_lyp(out / "layers.lyp")
    if pdk.layer_stack is not None:
        previous = active_pdk_or_none()
        try:  # the 2.5D script resolves layers through the *active* PDK
            pdk.activate(force=True)
            from gdsfactory.technology.klayout_tech import prefix_d25, suffix_d25

            script = pdk.layer_stack.get_klayout_3d_script(layer_views=pdk.get_layer_views())
            d25 = out / "d25" / f"{pdk.name}.lyd25"
            d25.parent.mkdir(parents=True, exist_ok=True)
            d25.write_text(prefix_d25 + script + suffix_d25, encoding="utf-8")
        except Exception as err:
            warnings.warn(f"2.5D script not written: {err}", stacklevel=2)
        finally:
            if previous is not None and previous is not pdk:
                previous.activate(force=True)
    return out


__all__ = [
    "DEFAULT_PROCESS",
    "activate_pdk",
    "active_pdk_or_none",
    "build_pdk",
    "ensure_pdk",
    "get_pdk",
    "layer_map_from_process",
    "layer_stack_from_process",
    "layer_views_from_process",
    "make_rib_pn",
    "upstream_pdk",
    "write_klayout_tech",
]
