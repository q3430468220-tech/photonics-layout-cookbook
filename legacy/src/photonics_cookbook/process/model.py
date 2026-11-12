"""Foundry process description ("process adapter") used by every recipe.

A *process* answers three questions that a gdsfactory ``Component`` alone does not:

1. **Which GDS layer plays which role?**  Device cells are written against *roles*
   (``core``, ``slab``, ``ppp``, ``via`` ...), never against raw layer numbers, so the
   same recipe can be re-targeted to another foundry by swapping one YAML file. Each
   layer also carries its *PDK name* (``WG``, ``NPP`` ...) and display style, from which
   :mod:`photonics_cookbook.pdk` builds a complete gdsfactory ``Pdk``.
2. **What is the vertical stack?**  ``zmin`` / ``thickness`` / material of each
   layer, plus unpatterned background layers (BOX, cladding ...).
3. **What do the simulators need?**  Lumerical material names for the optical
   solvers (FDTD / MODE) and for CHARGE, and dopant type / concentration of every
   implant layer.

Process files live in ``photonics_cookbook/process/data/*.yaml``; see
``_template.yaml`` there and ``docs/process-adapters.md``.

Conventions: lengths in micrometres, z = 0 at the BOX / device-silicon interface,
doping in cm^-3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import yaml

LayerKind = Literal["structure", "etch", "doping", "via", "metal", "annotation"]
LAYER_KINDS: tuple[str, ...] = ("structure", "etch", "doping", "via", "metal", "annotation")
SOLVER_KEYS: tuple[str, ...] = ("optical", "charge")

#: Canonical role names used by the device recipes. A process does not need to
#: define all of them -- recipes skip optional roles that a foundry does not offer.
STANDARD_ROLES: dict[str, str] = {
    "core": "full-thickness waveguide silicon",
    "slab": "partially etched (rib) silicon",
    "shallow_etch": "shallow etch, e.g. grating teeth",
    "n": "low-dose n implant (waveguide / junction)",
    "p": "low-dose p implant (waveguide / junction)",
    "np": "medium-dose n implant (N+)",
    "pp": "medium-dose p implant (P+)",
    "npp": "high-dose n implant for ohmic contact (N++)",
    "ppp": "high-dose p implant for ohmic contact (P++)",
    "via": "contact via from metal to silicon",
    "metal": "first metal / electrode layer",
    "heater": "resistive heater",
    "pad": "bond / probe pad metal or pad opening",
    "ge": "germanium absorber",
    "label": "text labels",
    "outline": "cell / floorplan outline",
}


class ProcessError(ValueError):
    """Raised when a process file is missing or inconsistent."""


def _f(value: Any, what: str) -> float:
    """Coerce YAML scalars to float.

    PyYAML follows YAML 1.1, where ``1.0e20`` (no exponent sign) is parsed as a
    *string*; ``float()`` accepts it, so we always convert explicitly.
    """
    try:
        return float(value)
    except (TypeError, ValueError) as err:
        raise ProcessError(f"{what}: expected a number, got {value!r}") from err


@dataclass(frozen=True)
class Material:
    """A material and its names in the Lumerical material databases."""

    key: str
    kind: Literal["dielectric", "semiconductor", "conductor"] = "dielectric"
    optical: str | None = None  # FDTD / MODE database name, e.g. "Si (Silicon) - Palik"
    charge: str | None = None  # CHARGE ("CT") database name, e.g. "Si (Silicon)"
    mesh_order: int = 2  # Lumerical mesh order: lower number = higher priority

    def name_for(self, solver: str) -> str:
        if solver not in SOLVER_KEYS:
            raise ProcessError(f"unknown solver {solver!r}; use one of {SOLVER_KEYS}")
        name = getattr(self, solver)
        if not name:
            raise ProcessError(f"material {self.key!r} has no Lumerical name for solver {solver!r}")
        return name


@dataclass(frozen=True)
class ProcessLayer:
    """One drawn GDS layer and its physical meaning."""

    role: str
    gds: tuple[int, int]
    kind: str
    name: str = ""  # layer name in the gdsfactory PDK / KLayout, e.g. "WG", "NPP"
    material: str | None = None
    zmin: float | None = None
    thickness: float | None = None
    depth: float | None = None  # etch depth (kind == "etch"), measured down from the top of `core`
    dopant: Literal["n", "p"] | None = None
    concentration: float | None = None  # cm^-3
    mesh_order: int | None = None
    description: str = ""
    color: str | None = None  # KLayout display colour, e.g. "#d94801"
    hatch: str | None = None  # KLayout dither pattern, e.g. "left-hatched"

    @property
    def zmax(self) -> float | None:
        if self.zmin is None or self.thickness is None:
            return None
        return self.zmin + self.thickness

    @property
    def gds_str(self) -> str:
        """Lumerical-style layer spec, e.g. ``"3:0"``."""
        return f"{self.gds[0]}:{self.gds[1]}"


@dataclass(frozen=True)
class BackgroundLayer:
    """Unpatterned layer (substrate, BOX, cladding ...)."""

    name: str
    material: str
    zmin: float
    zmax: float


@dataclass(frozen=True)
class Process:
    name: str
    layers: dict[str, ProcessLayer]
    materials: dict[str, Material]
    background: tuple[BackgroundLayer, ...] = ()
    description: str = ""
    foundry: str = ""
    platform: str = ""
    version: str = ""
    wavelength_um: float = 1.55
    references: tuple[str, ...] = ()
    upstream_pdk: dict[str, Any] = field(default_factory=dict)
    source: str = ""

    # ------------------------------------------------------------------ lookup
    def has(self, role: str) -> bool:
        return role in self.layers

    def layer(self, role: str) -> ProcessLayer:
        try:
            return self.layers[role]
        except KeyError:
            raise ProcessError(
                f"process {self.name!r} has no layer with role {role!r}. "
                f"Available roles: {', '.join(sorted(self.layers))}"
            ) from None

    def gds(self, role: str) -> tuple[int, int]:
        return self.layer(role).gds

    def layer_name(self, role: str) -> str:
        """PDK layer name of ``role`` (what you pass to gdsfactory, e.g. ``"NPP"``)."""
        return self.layer(role).name

    def by_name(self, name: str) -> ProcessLayer:
        for lay in self.layers.values():
            if lay.name == name:
                return lay
        raise ProcessError(f"process {self.name!r} has no layer named {name!r}")

    def role_of(self, gds: tuple[int, int]) -> str | None:
        for role, lay in self.layers.items():
            if lay.gds == tuple(gds):
                return role
        return None

    def by_kind(self, *kinds: str) -> list[ProcessLayer]:
        return [lay for lay in self.layers.values() if lay.kind in kinds]

    def material(self, key: str) -> Material:
        try:
            return self.materials[key]
        except KeyError:
            raise ProcessError(f"process {self.name!r}: unknown material {key!r}") from None

    def material_name(self, key: str, solver: str) -> str:
        return self.material(key).name_for(solver)

    def mesh_order(self, layer: ProcessLayer) -> int:
        if layer.mesh_order is not None:
            return layer.mesh_order
        if layer.material is None:
            return 2
        return self.material(layer.material).mesh_order

    @property
    def si_top(self) -> float:
        """Top of the full-thickness silicon (``core``) layer."""
        core = self.layer("core")
        assert core.zmax is not None
        return core.zmax

    @property
    def stack_zmin(self) -> float:
        zs = [b.zmin for b in self.background] + [
            lay.zmin for lay in self.layers.values() if lay.zmin is not None
        ]
        return min(zs) if zs else 0.0

    @property
    def stack_zmax(self) -> float:
        zs = [b.zmax for b in self.background] + [
            lay.zmax for lay in self.layers.values() if lay.zmax is not None
        ]
        return max(zs) if zs else 0.0

    # --------------------------------------------------------------- reporting
    def summary(self) -> str:
        lines = [f"Process '{self.name}'  {self.foundry} / {self.platform}  ({self.version})"]
        lines.append(f"  {'role':<13} {'PDK name':<10} {'GDS':>7}  {'kind':<10} {'z range / dose':<28} material")
        for lay in sorted(self.layers.values(), key=lambda x: x.gds):
            if lay.kind == "doping":
                zinfo = f"{lay.dopant}-type {lay.concentration:.2e} cm^-3"
            elif lay.kind == "etch":
                zinfo = f"etch depth {lay.depth:.3f} um"
            elif lay.zmin is not None:
                zinfo = f"z = {lay.zmin:.3f} .. {lay.zmax:.3f} um"
            else:
                zinfo = "-"
            lines.append(
                f"  {lay.role:<13} {lay.name:<10} {lay.gds_str:>7}  {lay.kind:<10} {zinfo:<28} {lay.material or ''}"
            )
        for b in self.background:
            lines.append(
                f"  {b.name:<13} {'-':<10} {'-':>7}  {'background':<10} z = {b.zmin:.3f} .. {b.zmax:.3f} um       {b.material}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------- loading
def _data_dir() -> Path:
    return Path(str(resources.files("photonics_cookbook.process") / "data"))


def available_processes() -> list[str]:
    """Names of the process files shipped with the cookbook."""
    return sorted(p.stem for p in _data_dir().glob("*.yaml") if not p.stem.startswith("_"))


def _parse_layer(role: str, d: dict[str, Any], default_name: str | None = None) -> ProcessLayer:
    where = f"layer {role!r}"
    if "gds" not in d:
        raise ProcessError(f"{where}: missing 'gds: [layer, datatype]'")
    gds = d["gds"]
    if not (isinstance(gds, list | tuple) and len(gds) == 2):
        raise ProcessError(f"{where}: 'gds' must be [layer, datatype], got {gds!r}")
    kind = str(d.get("kind", ""))
    if kind not in LAYER_KINDS:
        raise ProcessError(f"{where}: kind must be one of {LAYER_KINDS}, got {kind!r}")

    def opt(key: str) -> float | None:
        return None if d.get(key) is None else _f(d[key], f"{where}.{key}")

    dopant = d.get("dopant")
    if dopant is not None:
        dopant = str(dopant).lower()
        if dopant not in ("n", "p"):
            raise ProcessError(f"{where}: dopant must be 'n' or 'p', got {dopant!r}")
    layer = ProcessLayer(
        role=role,
        gds=(int(gds[0]), int(gds[1])),
        kind=kind,
        material=d.get("material"),
        zmin=opt("zmin"),
        thickness=opt("thickness"),
        depth=opt("depth"),
        dopant=dopant,  # type: ignore[arg-type]
        concentration=opt("concentration"),
        mesh_order=None if d.get("mesh_order") is None else int(d["mesh_order"]),
        description=str(d.get("description", "")).strip(),
        name=str(d.get("name") or default_name or role.upper()),
        color=None if d.get("color") is None else str(d["color"]),
        hatch=None if d.get("hatch") is None else str(d["hatch"]),
    )
    if not layer.name.isidentifier():
        raise ProcessError(f"{where}: PDK name {layer.name!r} must be a valid Python identifier")
    # kind-specific requirements
    need: dict[str, tuple[str, ...]] = {
        "structure": ("material", "zmin", "thickness"),
        "via": ("material", "zmin", "thickness"),
        "metal": ("material", "zmin", "thickness"),
        "etch": ("material", "depth"),
        "doping": ("dopant", "concentration"),
        "annotation": (),
    }
    missing = [k for k in need[kind] if getattr(layer, k) is None]
    if missing:
        raise ProcessError(f"{where} (kind={kind}) is missing: {', '.join(missing)}")
    return layer


def load_process(name_or_path: str | Path) -> Process:
    """Load a process by name (shipped YAML) or from a YAML file path."""
    path = Path(name_or_path)
    if not path.suffix:
        path = _data_dir() / f"{name_or_path}.yaml"
    if not path.exists():
        raise ProcessError(
            f"process file {str(name_or_path)!r} not found. Shipped processes: "
            f"{', '.join(available_processes())}"
        )
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ProcessError(f"{path}: top level must be a mapping")

    materials: dict[str, Material] = {}
    for key, m in (raw.get("materials") or {}).items():
        materials[key] = Material(
            key=key,
            kind=m.get("kind", "dielectric"),
            optical=m.get("optical"),
            charge=m.get("charge"),
            mesh_order=int(m.get("mesh_order", 2)),
        )

    # legacy: upstream_pdk.layer_names {role: NAME} -- prefer `name:` on each layer
    legacy_names = dict((raw.get("upstream_pdk") or {}).get("layer_names") or {})
    layers = {
        role: _parse_layer(role, d or {}, legacy_names.get(role))
        for role, d in (raw.get("layers") or {}).items()
    }

    background = tuple(
        BackgroundLayer(
            name=str(b["name"]),
            material=str(b["material"]),
            zmin=_f(b["zmin"], f"background {b.get('name')}.zmin"),
            zmax=_f(b["zmax"], f"background {b.get('name')}.zmax"),
        )
        for b in (raw.get("background") or [])
    )

    proc = Process(
        name=str(raw.get("name", path.stem)),
        layers=layers,
        materials=materials,
        background=background,
        description=str(raw.get("description", "")).strip(),
        foundry=str(raw.get("foundry", "")),
        platform=str(raw.get("platform", "")),
        version=str(raw.get("version", "")),
        wavelength_um=_f(raw.get("wavelength_um", 1.55), "wavelength_um"),
        references=tuple(raw.get("references") or ()),
        upstream_pdk=dict(raw.get("upstream_pdk") or {}),
        source=str(path),
    )
    validate_process(proc)
    return proc


def validate_process(proc: Process) -> None:
    """Consistency checks; raises :class:`ProcessError` on the first problem."""
    if "core" not in proc.layers:
        raise ProcessError(f"process {proc.name!r}: a 'core' layer is mandatory")
    seen: dict[tuple[int, int], str] = {}
    names: dict[str, str] = {}
    for role, lay in proc.layers.items():
        if lay.name in names:
            raise ProcessError(
                f"process {proc.name!r}: PDK name {lay.name!r} used by both {names[lay.name]!r} and {role!r}"
            )
        names[lay.name] = role
        if lay.gds in seen:
            raise ProcessError(
                f"process {proc.name!r}: GDS {lay.gds_str} used by both {seen[lay.gds]!r} and {role!r}"
            )
        seen[lay.gds] = role
        if lay.material is not None and lay.material not in proc.materials:
            raise ProcessError(
                f"process {proc.name!r}: layer {role!r} uses undefined material {lay.material!r}"
            )
        if lay.thickness is not None and lay.thickness <= 0:
            raise ProcessError(f"process {proc.name!r}: layer {role!r} thickness must be > 0")
        if lay.concentration is not None and not (1e10 < lay.concentration < 1e23):
            raise ProcessError(
                f"process {proc.name!r}: layer {role!r} concentration {lay.concentration:g} "
                "looks wrong -- use cm^-3 (e.g. 1.0e+18)"
            )
    for b in proc.background:
        if b.material not in proc.materials:
            raise ProcessError(
                f"process {proc.name!r}: background {b.name!r} uses undefined material {b.material!r}"
            )
        if b.zmax <= b.zmin:
            raise ProcessError(f"process {proc.name!r}: background {b.name!r} has zmax <= zmin")
