"""Link a process file to an installed gdsfactory PDK.

* :func:`check_against_pdk` -- compare the GDS numbers in a process YAML with the
  ``LAYER`` enum of the upstream PDK (e.g. ``cspdk``). Catches silent drift when the
  PDK is updated.
* :func:`bootstrap_from_pdk` -- draft a new process YAML from any gdsfactory PDK's
  ``LayerStack``; you then complete roles, Lumerical material names and doping.

gdsfactory is imported lazily so the rest of the package works without it.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from photonics_cookbook.process.model import Process, ProcessError

#: Best-guess Lumerical names for common gdsfactory material strings.
LUMERICAL_MATERIAL_GUESS: dict[str, dict[str, str]] = {
    "si": {"optical": "Si (Silicon) - Palik", "charge": "Si (Silicon)", "kind": "semiconductor"},
    "sio2": {"optical": "SiO2 (Glass) - Palik", "charge": "SiO2 (Glass) - Sze", "kind": "dielectric"},
    "sin": {"optical": "Si3N4 (Silicon Nitride) - Phillip", "charge": "Si3N4 (Silicon Nitride) - Sze", "kind": "dielectric"},
    "ge": {"optical": "Ge (Germanium) - Palik", "charge": "Ge (Germanium)", "kind": "semiconductor"},
    "al": {"optical": "Al (Aluminium) - CRC", "charge": "Al (Aluminium) - CRC", "kind": "conductor"},
    "cu": {"optical": "Cu (Copper) - CRC", "charge": "Cu (Copper) - CRC", "kind": "conductor"},
    "tin": {"optical": "TiN - Palik", "charge": "TiN", "kind": "conductor"},
    "w": {"optical": "W (Tungsten) - Palik", "charge": "W (Tungsten) - CRC", "kind": "conductor"},
    "air": {"optical": "etch", "charge": "Air", "kind": "dielectric"},
}


def layer_tuple(spec: Any) -> tuple[int, int] | None:
    """Best effort conversion of a gdsfactory/kfactory layer spec to ``(layer, datatype)``."""
    if spec is None:
        return None
    if isinstance(spec, tuple | list) and len(spec) == 2 and all(isinstance(v, int) for v in spec):
        return int(spec[0]), int(spec[1])
    lay = getattr(spec, "layer", None)
    dt = getattr(spec, "datatype", None)
    if isinstance(lay, int) and isinstance(dt, int):
        return lay, dt
    if lay is not None and lay is not spec:  # e.g. LogicalLayer(layer=LAYER.WG)
        return layer_tuple(lay)
    try:
        t = tuple(spec)
    except TypeError:
        return None
    if len(t) == 2:
        try:
            return int(t[0]), int(t[1])
        except (TypeError, ValueError):
            return None
    return None


def import_pdk(modules: Iterable[str]) -> tuple[str, Any]:
    """Import the first module that exposes a ``PDK`` object."""
    errors = []
    for mod in modules:
        try:
            m = importlib.import_module(mod)
        except Exception as err:  # ImportError, or errors raised while building the PDK
            errors.append(f"{mod}: {type(err).__name__}: {err}")
            continue
        pdk = getattr(m, "PDK", None)
        if pdk is not None:
            return mod, pdk
        errors.append(f"{mod}: no 'PDK' attribute")
    raise ProcessError("could not import a gdsfactory PDK: " + " | ".join(errors))


@dataclass
class LayerCheck:
    role: str
    process_gds: tuple[int, int]
    pdk_name: str
    pdk_gds: tuple[int, int] | None

    @property
    def ok(self) -> bool:
        return self.pdk_gds == self.process_gds


def check_against_pdk(process: Process) -> tuple[str, list[LayerCheck]]:
    """Compare ``process`` with its ``upstream_pdk``; returns (module, checks)."""
    up = process.upstream_pdk
    if not up:
        raise ProcessError(f"process {process.name!r} declares no upstream_pdk")
    modules = up.get("modules") or [up.get("module") or up.get("python_package")]
    module, pdk = import_pdk(modules)
    layers = getattr(pdk, "layers", None)
    checks = []
    for role, name in (up.get("layer_names") or {}).items():
        spec = getattr(layers, name, None) if layers is not None else None
        checks.append(LayerCheck(role, process.gds(role), name, layer_tuple(spec)))
    return module, checks


def bootstrap_from_pdk(module: str) -> dict[str, Any]:
    """Draft a process dictionary (ready for ``yaml.safe_dump``) from a PDK's LayerStack."""
    mod, pdk = import_pdk([module])
    stack = getattr(pdk, "layer_stack", None)
    levels: dict[str, Any] = dict(getattr(stack, "layers", {}) or {}) if stack is not None else {}

    used_materials: set[str] = set()
    layers: dict[str, Any] = {}
    referenced: set[tuple[int, int]] = set()
    for name, lvl in levels.items():
        gds = layer_tuple(getattr(lvl, "layer", None))
        mat = str(getattr(lvl, "material", "") or "").lower() or "TODO"
        thickness = getattr(lvl, "thickness", None)
        zmin = getattr(lvl, "zmin", None)
        role = name.lower()
        entry: dict[str, Any] = {}
        if gds is None:
            entry["gds"] = "TODO  # derived / boolean layer in the PDK -- draw-able layer?"
        else:
            entry["gds"] = list(gds)
            referenced.add(gds)
        if "via" in role:
            kind = "via"
        elif mat in ("al", "cu", "tin", "w", "aluminum", "copper"):
            kind = "metal"
        else:
            kind = "structure"
        entry.update(kind=kind, material=mat, zmin=zmin, thickness=thickness)
        layers[role] = entry
        used_materials.add(mat)

    # PDK layers that the stack does not reference: often implants, labels, DRC helpers.
    enum = getattr(pdk, "layers", None)
    for attr in dir(enum) if enum is not None else []:
        if attr.startswith("_"):
            continue
        gds = layer_tuple(getattr(enum, attr, None))
        if gds is None or gds in referenced:
            continue
        layers[attr.lower()] = {
            "gds": list(gds),
            "kind": "annotation",
            "description": "TODO: not in the LayerStack -- implant? label? set kind/dopant/concentration",
        }
        referenced.add(gds)

    materials = {}
    for mat in sorted(used_materials):
        guess = LUMERICAL_MATERIAL_GUESS.get(mat, {})
        materials[mat] = {
            "kind": guess.get("kind", "dielectric"),
            "optical": guess.get("optical", "TODO"),
            "charge": guess.get("charge", "TODO"),
        }
    return {
        "name": f"{mod.replace('.', '_')}_TODO",
        "foundry": "TODO",
        "platform": "TODO",
        "version": "bootstrapped from " + mod,
        "wavelength_um": 1.55,
        "upstream_pdk": {"python_package": mod.split(".")[0], "modules": [mod]},
        "materials": materials,
        "background": [
            {"name": "box", "material": "sio2", "zmin": -2.0, "zmax": 0.0},
            {"name": "clad", "material": "sio2", "zmin": 0.0, "zmax": 2.0},
        ],
        "layers": layers,
    }
