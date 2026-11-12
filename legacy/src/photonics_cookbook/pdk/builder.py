"""Build a gdsfactory ``Pdk`` from a cookbook process file.

A gdsfactory PDK (https://gdsfactory.github.io/gdsfactory/notebooks/08_pdk.html)
bundles everything gdsfactory needs to know about a foundry:

=================  ====================================================  ===================================
part               what it is                                            built here from
=================  ====================================================  ===================================
``layers``         LayerMap: layer *name* -> (GDS layer, datatype)        ``name`` + ``gds`` of each layer
``layer_stack``    LayerStack: z-extent, material, mesh order per level   ``zmin``/``thickness``, ``background``
``layer_views``    LayerViews: KLayout colours / patterns (.lyp)          ``color``/``hatch`` (+ upstream views)
``cross_sections`` named waveguide / wire profiles (list of Sections)    ``rib_pn`` from :mod:`..devices.pn_waveguide`
``cells``          parametric cells (``@gf.cell`` functions)              cookbook cells + upstream cells
``models``,        circuit models, routing, layer transitions,           taken over from the upstream PDK
``routing_*`` ...  connectivity                                          (e.g. ``cspdk.si220``)
=================  ====================================================  ===================================

The process file is the single source of truth: the same YAML also drives the
Lumerical bridge, and every ``LayerLevel`` carries the Lumerical material names in
``info`` so downstream tools can read them from the PDK as well.

If the process names an ``upstream_pdk`` (cspdk for CORNERSTONE), the cookbook PDK
*extends* it through ``Pdk(base_pdks=[upstream])``: all upstream cells and
cross-sections keep working, and the extra layers (implants, vias, metal) are added.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import gdsfactory as gf
import kfactory as kf
from gdsfactory.technology import LayerLevel, LayerStack, LayerView, LayerViews, LogicalLayer

from photonics_cookbook.devices.pn_waveguide import pn_rib_sections
from photonics_cookbook.process import Process, ProcessError, load_process
from photonics_cookbook.process.upstream import import_pdk, layer_tuple

DEFAULT_PROCESS = "cornerstone_si220_active"

#: KLayout display defaults for roles that the process file gives no style for.
DEFAULT_VIEWS: dict[str, tuple[str, str]] = {
    "core": ("#ff9d9d", "coarsely dotted"),
    "slab": ("silver", "coarsely dotted"),
    "shallow_etch": ("blue", "coarsely dotted"),
    "n": ("#fdae6b", "left-hatched"),
    "p": ("#a1d99b", "right-hatched"),
    "np": ("#fd8d3c", "left-hatched"),
    "pp": ("#74c476", "right-hatched"),
    "npp": ("#d94801", "strongly left-hatched dense"),
    "ppp": ("#238b45", "strongly right-hatched dense"),
    "via": ("#252525", "cross-hatched"),
    "metal": ("#969696", "dotted"),
    "heater": ("#ebc634", "coarsely dotted"),
    "pad": ("teal", "coarsely dotted"),
    "ge": ("#8c6bb1", "left-hatched"),
    "outline": ("green", "hollow"),
    "label": ("cyan", "hollow"),
}


# --------------------------------------------------------------------------- layers
def layer_map_from_process(
    process: Process, base_layers: type[gf.LayerEnum] | None = None, name: str | None = None
) -> type[gf.LayerEnum]:
    """LayerMap (a kfactory ``LayerEnum``) = upstream layers + the process layers.

    Equivalent to writing ``class LayerMapX(gf.technology.LayerMap): WG = (3, 0) ...``
    by hand (see ``examples/00_getting_started/01_define_your_pdk.py``), but generated
    so that the YAML file stays the single source of truth.
    """
    entries: dict[str, tuple[int, int]] = {}
    if base_layers is not None:
        for member_name, member in base_layers.__members__.items():  # includes aliases
            gds = layer_tuple(member)
            if gds is not None:
                entries[str(member_name)] = gds
    for lay in process.layers.values():
        if lay.name in entries:
            if entries[lay.name] != lay.gds:
                raise ProcessError(
                    f"layer {lay.name!r}: process says {lay.gds}, upstream PDK says "
                    f"{entries[lay.name]} -- fix the process YAML"
                )
            continue
        entries[lay.name] = lay.gds
    infos = kf.LayerInfos(**{n: kf.kdb.LayerInfo(ly, dt) for n, (ly, dt) in entries.items()})
    return gf.kcl.layerenum_from_dict(name=name or f"LayerMap_{process.name}", layers=infos)


def _lumerical_info(process: Process, material: str, role: str) -> dict[str, Any]:
    mat = process.material(material)
    return {"role": role, "lumerical_optical": mat.optical, "lumerical_charge": mat.charge}


def _level(**kwargs: Any) -> LayerLevel:
    try:
        return LayerLevel(**kwargs)
    except Exception:  # older gdsfactory without `background`
        if kwargs.pop("background", None) is None:
            raise
        return LayerLevel(**kwargs)


def layer_stack_from_process(process: Process) -> LayerStack:
    """LayerStack (3D view, gplugins solvers) from the process z-stack.

    Partial etches are modelled like cspdk does it: ``core`` becomes ``WG - GRA``
    (full height) and an extra level ``WG & GRA`` has the etched height. Implants
    are not 3D layers; their doses stay in the process file (used by CHARGE).
    """
    # LogicalLayer takes the GDS tuple (not the name): gdsfactory's 3D export (c.to_3d())
    # only accepts tuples / LayerEnum members there.
    core = process.layer("core")
    core_logical = LogicalLayer(layer=core.gds)
    etches = process.by_kind("etch")
    levels: dict[str, LayerLevel] = {}

    for i, b in enumerate(process.background):
        mat = process.material(b.material)
        levels[b.name] = _level(
            name=b.name,
            layer=core_logical,
            zmin=b.zmin,
            thickness=b.zmax - b.zmin,
            material=b.material,
            mesh_order=100 + i if b.material == core.material else 10 + i,
            background=True,
            info=_lumerical_info(process, b.material, "background") | {"lumerical_mesh_order": mat.mesh_order},
        )

    for lay in process.layers.values():
        if lay.kind in ("doping", "annotation", "etch"):
            continue
        assert lay.material is not None and lay.zmin is not None and lay.thickness is not None
        logical = LogicalLayer(layer=lay.gds)
        kwargs: dict[str, Any] = {}
        layer_expr: Any = logical
        if lay.role == "core" and etches:
            for e in etches:
                layer_expr = layer_expr - LogicalLayer(layer=e.gds)
            kwargs["derived_layer"] = logical
        levels[lay.role] = _level(
            name=lay.role,
            layer=layer_expr,
            zmin=lay.zmin,
            thickness=lay.thickness,
            material=lay.material,
            mesh_order=process.mesh_order(lay),
            info=_lumerical_info(process, lay.material, lay.role),
            **kwargs,
        )

    for e in etches:
        assert e.depth is not None and core.zmin is not None
        levels[e.role] = LayerLevel(
            name=e.role,
            layer=core_logical & LogicalLayer(layer=e.gds),
            derived_layer=LogicalLayer(layer=e.gds),
            zmin=core.zmin,
            thickness=process.si_top - e.depth - core.zmin,
            material=core.material,
            mesh_order=max(process.mesh_order(core) - 1, 1),
            info=_lumerical_info(process, core.material, e.role) | {"etch_depth_um": e.depth},  # type: ignore[arg-type]
        )
    return LayerStack(layers=levels)


def layer_views_from_process(process: Process, base_views: LayerViews | None = None) -> LayerViews:
    """LayerViews (KLayout .lyp): upstream views + a view for every new process layer."""
    views = LayerViews(
        custom_dither_patterns=dict(base_views.custom_dither_patterns) if base_views else {},
        custom_line_styles=dict(base_views.custom_line_styles) if base_views else {},
    )
    if base_views is not None:
        for view_name, view in base_views.layer_views.items():
            views.add_layer_view(name=view_name, layer_view=view)
    taken = set(views.layer_views)
    taken_gds = {tuple(v.layer) for v in views.layer_views.values() if v.layer is not None}
    for lay in process.layers.values():
        if lay.name in taken or lay.gds in taken_gds:
            continue
        color, hatch = DEFAULT_VIEWS.get(lay.role, ("magenta", "dotted"))
        views.add_layer_view(
            name=lay.name,
            layer_view=LayerView(
                layer=lay.gds,
                color=lay.color or color,
                hatch_pattern=lay.hatch or hatch,
                layer_in_name=True,
                transparent=lay.kind == "doping",
                width=1,
            ),
        )
    return views


# -------------------------------------------------------------------- cross-sections
def make_rib_pn(process: Process) -> Callable[..., gf.CrossSection]:
    """Return the ``rib_pn`` cross-section factory bound to ``process``."""

    def rib_pn(
        width: float = 0.5,
        junction_offset: float = 0.0,
        contact_spacing: float = 0.8,
        contact_width: float = 2.0,
        via_enclosure: float = 0.5,
        implant_overlap: float = 0.2,
        mid_spacing: float = 0.4,
        slab_margin: float = 0.5,
        flip: bool = False,
        radius: float | None = 25.0,
    ) -> gf.CrossSection:
        """Lateral PN rib waveguide: core + slab + N/P + N++/P++ + vias + metal.

        Geometry: :func:`photonics_cookbook.devices.pn_waveguide.pn_rib_sections`.
        Electrical ports ``n1/n2`` and ``p1/p2`` sit on the metal stripes.
        """
        specs = pn_rib_sections(
            process,
            width=width,
            junction_offset=junction_offset,
            contact_spacing=contact_spacing,
            contact_width=contact_width,
            via_enclosure=via_enclosure,
            implant_overlap=implant_overlap,
            mid_spacing=mid_spacing,
            slab_margin=slab_margin,
            flip=flip,
        )
        core, rest = specs[0], specs[1:]
        sections = tuple(
            gf.Section(
                width=sp.width,
                offset=sp.offset,
                layer=process.layer_name(sp.role),
                name=sp.name,
                port_names=sp.port_names,
                port_types=sp.port_types,
            )
            for sp in rest
        )
        return gf.cross_section.cross_section(
            width=core.width,
            layer=process.layer_name("core"),
            sections=sections,
            port_names=("o1", "o2"),
            radius=radius,
            radius_min=radius,
        )

    return rib_pn


# ------------------------------------------------------------------------------ PDK
def _is_shipped(process: Process, name: str) -> bool:
    """True if ``process`` is the shipped process file ``name`` (not a same-named copy)."""
    from photonics_cookbook.process.model import _data_dir

    src = Path(process.source)
    return src.stem == name and src.parent.resolve() == _data_dir().resolve()


def _cookbook_cells(process: Process) -> dict[str, Callable[..., gf.Component]]:
    from photonics_cookbook import cells as cookbook_cells  # lazy: cells imports this package

    cells: dict[str, Callable[..., gf.Component]] = {}
    for cell_name in cookbook_cells.CELLS:
        func = getattr(cookbook_cells, cell_name)
        # cells default to the shipped CORNERSTONE file; bind any other process explicitly
        cells[cell_name] = func if _is_shipped(process, DEFAULT_PROCESS) else partial(func, process=process.source)
    return cells


def upstream_pdk(process: Process) -> gf.Pdk | None:
    """The gdsfactory PDK this process extends, or ``None`` (with a warning) if unavailable."""
    modules = list(process.upstream_pdk.get("modules") or [])
    if not modules:
        return None
    try:
        return import_pdk(modules)[1]
    except ProcessError as err:
        warnings.warn(f"building {process.name!r} without its upstream PDK: {err}", stacklevel=2)
        return None


def build_pdk(process: str | Process = DEFAULT_PROCESS, extend_upstream: bool = True) -> gf.Pdk:
    """Build (but do not activate) the cookbook PDK for ``process``."""
    proc = process if isinstance(process, Process) else load_process(process)
    base = upstream_pdk(proc) if extend_upstream else None

    layers = layer_map_from_process(proc, base.layers if base is not None else None)
    stack = layer_stack_from_process(proc)
    base_views = None
    if base is not None and base.layer_views is not None:
        base_views = base.get_layer_views()
    views = layer_views_from_process(proc, base_views)

    cross_sections: dict[str, Callable[..., gf.CrossSection]] = {}
    default_names: dict[str, str] = {}
    if all(proc.has(r) for r in ("core", "slab", "n", "p")):
        rib_pn = make_rib_pn(proc)
        cross_sections["rib_pn"] = rib_pn
        # gdsfactory names the default instance after the factory (like @xsection does)
        default_names[rib_pn().name] = "rib_pn"

    kwargs: dict[str, Any] = {}
    if base is not None:
        kwargs = {
            "base_pdks": [base],
            "models": dict(base.models),
            "connectivity": base.connectivity,
            "routing_strategies": base.routing_strategies,
            "layer_transitions": dict(base.layer_transitions),
            "constants": base.constants,
        }
    return gf.Pdk(
        name=proc.name,
        version=proc.version,
        layers=layers,
        layer_stack=stack,
        layer_views=views,
        cross_sections=cross_sections,
        cross_section_default_names=default_names,
        cells=_cookbook_cells(proc),
        **kwargs,
    )
