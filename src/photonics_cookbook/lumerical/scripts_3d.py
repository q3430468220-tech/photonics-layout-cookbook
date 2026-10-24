"""3D layout import into Lumerical FDTD / MODE.

Two routes, both driven by the GDS + process file:

``geometry3d`` / ``fdtd3d`` (robust, all versions)
    One ``gdsimport(file, cell, "L:D", material, zmin, zmax)`` per drawn layer, plus
    background slabs (BOX, cladding ...). ``fdtd3d`` adds an FDTD region sized to the
    optical layers and one port per optical port of the component.

``layerbuilder`` (Ansys' process-file route)
    Builds a Layer Builder object from script, slicing the stack into
    non-overlapping z-layers whose patterns are Boolean expressions of GDS layers
    (rib = ``3:0 or 5:0`` below the slab top, ``3:0`` above it), then calls
    ``saveprocessfile`` so Lumerical writes the ``.lbr`` itself. Re-use that .lbr in
    any FDTD / MODE project via ``loadprocessfile``. We deliberately do *not* write
    the .lbr XML by hand: its schema is not publicly documented.
"""

from __future__ import annotations

from dataclasses import dataclass

from photonics_cookbook.lumerical.lsf import ASCII_PATH_NOTE, header, ident, num, q, um
from photonics_cookbook.process import Process


@dataclass(frozen=True)
class OpticalPort:
    name: str
    x: float
    y: float
    width: float
    orientation: float  # degrees, pointing out of the device


Bbox = tuple[float, float, float, float]


Present = set[tuple[int, int]] | None  # GDS layers that actually contain shapes


def _layers_for_3d(process: Process, include_metal: bool, present: Present = None):
    kinds = ["structure", "etch"] + (["via", "metal"] if include_metal else [])
    return [
        lay
        for lay in process.layers.values()
        if lay.kind in kinds and (present is None or lay.gds in present)
    ]


def _geometry_block(
    gds_name: str,
    cell: str,
    process: Process,
    bbox: Bbox,
    include_metal: bool,
    present: Present = None,
    margin: float = 2.0,
) -> list[str]:
    x0, y0, x1, y1 = bbox
    x0, y0, x1, y1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin
    L = [
        "###############################################################################",
        "# 1. Background (unpatterned) layers",
        "###############################################################################",
        "function bg_rect(name, mat, x0, x1, y0, y1, z0, z1, mo) {",
        "    addrect;",
        '    set("name", name);',
        '    set("material", mat);',
        '    set("x min", x0);  set("x max", x1);',
        '    set("y min", y0);  set("y max", y1);',
        '    set("z min", z0);  set("z max", z1);',
        '    set("override mesh order from material database", 1);',
        '    set("mesh order", mo);',
        '    try { set("alpha", 0.15); } catch(err_alpha);',
        "    return 1;",
        "}",
    ]
    for b in process.background:
        mat = process.material(b.material)
        L.append(
            f"bg_rect({q(ident(b.name))}, {q(mat.name_for('optical'))}, {um(x0)}, {um(x1)}, "
            f"{um(y0)}, {um(y1)}, {um(b.zmin)}, {um(b.zmax)}, {max(mat.mesh_order, 3)});"
        )
    L += [
        "",
        "###############################################################################",
        "# 2. Drawn layers: gdsimport(file, cell, 'layer:datatype', material, zmin, zmax)",
        "#    (lower mesh order wins where objects overlap: metal 1 < Si 2 < oxide 3)",
        "###############################################################################",
        f"gds_file = {q(gds_name)};",
        f"cell     = {q(cell)};",
        "n_total  = 0;",
        "function gds_layer(fname, cname, spec, mat, z0, z1) {",
        "    n = 0;  err_gi = \"\";",
        "    try { n = gdsimport(fname, cname, spec, mat, z0, z1); } catch(err_gi);",
        '    if (length(err_gi) > 0) { ?"  gdsimport failed for " + spec + ": " + err_gi; }',
        '    if (n == 0) { ?"  (no shapes imported for " + spec + ")"; }',
        "    return n;",
        "}",
    ]
    etch_fill_done = set()
    for lay in _layers_for_3d(process, include_metal, present):
        mat = process.material(lay.material)  # type: ignore[arg-type]
        if lay.kind == "etch":
            z_lo, z_hi = process.si_top - lay.depth, process.si_top  # type: ignore[operator]
            fill = f"etchfill_{ident(mat.key)}"
            if fill not in etch_fill_done:
                etch_fill_done.add(fill)
                L += [
                    f"# etch layer: filled with a copy of {mat.name_for('optical')} that has mesh order 1",
                    "ef_ok = 0;",
                    f'try {{ setmaterial({q(fill)}, "mesh order", 1); ef_ok = 1; }} catch(err_ef);',
                    "if (ef_ok == 0) {",
                    f"    try {{ tmp = copymaterial({q(mat.name_for('optical'))}); setmaterial(tmp, \"name\", {q(fill)});",
                    f'          setmaterial({q(fill)}, "mesh order", 1); ef_ok = 1; }} catch(err_ef2);',
                    "}",
                    f'if (ef_ok == 0) {{ ?"WARNING: could not create {fill} -- etch layer will not override Si."; }}',
                ]
            L += [
                f"n = gds_layer(gds_file, cell, {q(lay.gds_str)}, {q(fill)}, {um(z_lo)}, {um(z_hi)});",
                f'?"{lay.role:<12} ({lay.gds_str}) etch {lay.depth} um : " + num2str(n) + " polygons";',
                "n_total = n_total + n;",
            ]
        else:
            L += [
                f"n = gds_layer(gds_file, cell, {q(lay.gds_str)}, {q(mat.name_for('optical'))}, "
                f"{um(lay.zmin)}, {um(lay.zmax)});",
                f'?"{lay.role:<12} ({lay.gds_str}) z = {lay.zmin:g}..{lay.zmax:g} um : " + num2str(n) + " polygons";',
                "n_total = n_total + n;",
            ]
    L += [
        'if (n_total == 0) { ?"WARNING: nothing imported -- check the cell name and GDS layers."; }',
        "",
    ]
    return L


def _port_frame(ports: list[OpticalPort], bbox: Bbox, inset: float, margin: float):
    """FDTD span: optical bbox + margin, pulled inside each port so waveguides cross the PML."""
    x0, y0, x1, y1 = bbox[0] - margin, bbox[1] - margin, bbox[2] + margin, bbox[3] + margin
    for p in ports:
        o = round(p.orientation) % 360
        if o == 180:
            x0 = max(x0, p.x + inset)
        elif o == 0:
            x1 = min(x1, p.x - inset)
        elif o == 90:
            y1 = min(y1, p.y - inset)
        elif o == 270:
            y0 = max(y0, p.y + inset)
        else:
            raise ValueError(f"port {p.name}: only Manhattan ports are supported (got {p.orientation})")
    return x0, y0, x1, y1


def geometry3d_lsf(
    gds_name: str,
    cell: str,
    process: Process,
    bbox: Bbox,
    include_metal: bool = True,
    clear: bool = True,
    present: Present = None,
) -> str:
    """Geometry-only import (FDTD or MODE). Add your own solver region afterwards."""
    text = header(
        f"3D geometry import: {cell}",
        [
            f"Process : {process.name}  ({process.foundry})",
            f"GDS     : {gds_name}",
            "Use     : FDTD or MODE -> Script file editor -> Run (or lumapi .feval()).",
            ASCII_PATH_NOTE,
        ],
    )
    L = [] if not clear else ["switchtolayout;", "deleteall;"]
    L += ["try { cd(filedirectory(currentscriptname)); } catch(err_cd);", "um = 1e-6;", ""]
    L += _geometry_block(gds_name, cell, process, bbox, include_metal, present)
    return text + "\n".join(L) + "\n"


def fdtd3d_lsf(
    gds_name: str,
    cell: str,
    process: Process,
    bbox_all: Bbox,
    bbox_optical: Bbox,
    ports: list[OpticalPort],
    wavelength_span_um: tuple[float, float] = (1.50, 1.60),
    include_metal: bool = True,
    mesh_accuracy: int = 2,
    sim_time_ps: float = 10.0,
    source_port: str | None = None,
    save_as: str | None = None,
    run: bool = False,
    present: Present = None,
) -> str:
    """Geometry + 3D FDTD region + ports (S-parameter ready)."""
    if not ports:
        raise ValueError("fdtd3d needs at least one optical port")
    si_top = process.si_top
    zr0, zr1 = -0.8, si_top + 0.8  # stay inside BOX / cladding
    x0, y0, x1, y1 = _port_frame(ports, bbox_optical, inset=1.0, margin=1.0)
    text = header(
        f"3D FDTD set-up: {cell}",
        [
            f"Process : {process.name}  ({process.foundry})",
            f"GDS     : {gds_name}",
            f"Ports   : {', '.join(p.name for p in ports)}  (source: {source_port or ports[0].name})",
            "Use     : open Lumerical FDTD -> run this script (or lumapi FDTD().feval()).",
            "Tip     : full 3D FDTD of a resonator is slow; for ring spectra prefer",
            "          MODE varFDTD, or FDTD of the coupler + FDE of the ring waveguide",
            "          (the Ansys Ring Modulator workflow).",
            ASCII_PATH_NOTE,
        ],
    )
    L = ["switchtolayout;", "deleteall;", "try { cd(filedirectory(currentscriptname)); } catch(err_cd);", "um = 1e-6;", ""]
    L += _geometry_block(gds_name, cell, process, bbox_all, include_metal, present)
    L += [
        "###############################################################################",
        "# 3. FDTD region (waveguides run through the PML at every port)",
        "###############################################################################",
        "addfdtd;",
        'set("dimension", "3D");',
        f'set("x min", {um(x0)});  set("x max", {um(x1)});',
        f'set("y min", {um(y0)});  set("y max", {um(y1)});',
        f'set("z min", {um(zr0)});  set("z max", {um(zr1)});',
        f'set("mesh accuracy", {int(mesh_accuracy)});',
        f'set("simulation time", {num(sim_time_ps * 1e-12)});',
        f'setglobalsource("wavelength start", {um(wavelength_span_um[0])});',
        f'setglobalsource("wavelength stop", {um(wavelength_span_um[1])});',
        'setglobalmonitor("frequency points", 201);',
        "",
        "# field profile in the middle of the silicon",
        "addprofile;",
        'set("name", "field_xy");',
        'set("monitor type", "2D Z-normal");',
        f'set("x min", {um(x0)});  set("x max", {um(x1)});',
        f'set("y min", {um(y0)});  set("y max", {um(y1)});',
        f'set("z", {um(si_top / 2)});',
        "",
        "###############################################################################",
        "# 4. Ports (one per optical port of the gdsfactory component)",
        "###############################################################################",
    ]
    port_off = 0.3
    zc, zs = 0.5 * (zr0 + zr1), (zr1 - zr0) - 0.2
    for p in ports:
        o = round(p.orientation) % 360
        axis = "x-axis" if o in (0, 180) else "y-axis"
        direction = "Forward" if o in (180, 270) else "Backward"
        span = p.width + 3.0
        if o == 180:
            px, py = x0 + port_off, p.y
        elif o == 0:
            px, py = x1 - port_off, p.y
        elif o == 270:
            px, py = p.x, y0 + port_off
        else:
            px, py = p.x, y1 - port_off
        L += [
            "addport;",
            f'set("name", {q(p.name)});',
            f'set("injection axis", {q(axis)});',
            f'set("direction", {q(direction)});',
            f'set("x", {um(px)});  set("y", {um(py)});  set("z", {um(zc)});',
            (f'set("y span", {um(span)});' if axis == "x-axis" else f'set("x span", {um(span)});'),
            f'set("z span", {um(zs)});',
            'try { set("mode selection", "fundamental TE mode"); } catch(err_ms);',
        ]
    src = source_port or ports[0].name
    L += [f'try {{ select("FDTD::ports"); set("source port", {q(src)}); }} catch(err_sp);', ""]
    fsp = save_as or f"{ident(cell)}_fdtd.fsp"
    L += [f"save({q(fsp)});", f'?"Saved {fsp}. Run it, or use the S-parameter sweep for the full matrix.";']
    if run:
        L += [
            "run;",
            "f = getresult(\"FDTD::ports::" + ports[-1].name + "\", \"T\");",
            'plot(f.lambda*1e9, abs(f.T), "wavelength (nm)", "T", "transmission to last port");',
        ]
    return text + "\n".join(L) + "\n"


# ----------------------------------------------------------------- layer builder
@dataclass(frozen=True)
class BuilderLayer:
    name: str
    z0: float
    z1: float
    background: str | None  # material key
    pattern: str | None  # material key
    expression: str | None  # Boolean GDS expression, e.g. "(3:0 or 5:0)"


def builder_slices(
    process: Process, include_metal: bool = False, present: Present = None
) -> list[BuilderLayer]:
    """Slice the stack into contiguous, non-overlapping z-layers for the Layer Builder.

    ``present`` (GDS layers that contain shapes) drops unused layers from the Boolean
    expressions; pass ``None`` to build a generic process file for the whole platform.
    """

    def used(lay) -> bool:
        return present is None or lay.gds in present

    drawn = [
        lay
        for lay in process.layers.values()
        if (lay.kind == "structure" or (include_metal and lay.kind in ("via", "metal"))) and used(lay)
    ]
    etches = [lay for lay in process.layers.values() if lay.kind == "etch" and used(lay)]
    zs = {b.zmin for b in process.background} | {b.zmax for b in process.background}
    for lay in drawn:
        zs |= {lay.zmin, lay.zmax}  # type: ignore[arg-type]
    for e in etches:
        zs |= {process.si_top - e.depth, process.si_top}  # type: ignore[operator]
    z = sorted(round(v, 6) for v in zs)
    out: list[BuilderLayer] = []
    for k, (za, zb) in enumerate(zip(z[:-1], z[1:], strict=True)):
        zm = 0.5 * (za + zb)
        bg = next((b.material for b in process.background if b.zmin <= zm <= b.zmax), None)
        by_mat: dict[str, list[str]] = {}
        for lay in drawn:
            if lay.zmin <= zm <= lay.zmax:  # type: ignore[operator]
                by_mat.setdefault(lay.material, []).append(lay.gds_str)  # type: ignore[arg-type]
        cut = [e.gds_str for e in etches if process.si_top - e.depth <= zm <= process.si_top]  # type: ignore[operator]
        if not by_mat:
            if bg is not None:
                out.append(BuilderLayer(ident(f"L{k:02d}_{bg}"), za, zb, bg, None, None))
            continue
        for mat, gds_list in by_mat.items():
            base = "(" + " or ".join(gds_list) + ")"
            expr = base if not cut else f"{base} xor ({base} and ({' or '.join(cut)}))"
            out.append(BuilderLayer(ident(f"L{k:02d}_{mat}"), za, zb, bg, mat, expr))
    return out


def layerbuilder_lsf(
    gds_name: str,
    cell: str,
    process: Process,
    lbr_name: str | None = None,
    include_metal: bool = False,
    present: Present = None,
) -> str:
    """Layer Builder set-up + ``saveprocessfile`` (Lumerical writes the .lbr)."""
    slices = builder_slices(process, include_metal=include_metal, present=present)
    lbr = lbr_name or f"{process.name}.lbr"
    z_bottom = slices[0].z0
    multi = len({(s.z0, s.z1) for s in slices}) != len(slices)
    text = header(
        f"Layer Builder + process file: {process.name}",
        [
            f"GDS     : {gds_name}   cell: {cell}",
            f"Writes  : {lbr}  (via saveprocessfile -- the format is Lumerical's own)",
            "Use     : FDTD or MODE (2022 R1+). Afterwards any project can do",
            f'            addlayerbuilder; loadgdsfile("x.gds"); loadprocessfile("{lbr}");',
            "Status  : EXPERIMENTAL -- some Layer Builder property names differ between",
            "          versions; every uncertain call is wrapped in try{} and reported.",
            "Slices (bottom -> top, contiguous, so 'Auto' start positions are correct):",
            *[
                f"  {s.name:<18} z = {s.z0:+.3f} .. {s.z1:+.3f} um  "
                + (f"{s.pattern} on {s.expression}, rest {s.background}" if s.pattern else f"{s.background}")
                for s in slices
            ],
            ASCII_PATH_NOTE,
        ],
    )
    L = [
        "switchtolayout;",
        "try { cd(filedirectory(currentscriptname)); } catch(err_cd);",
        "um = 1e-6;",
        "",
        "addlayerbuilder;",
        'set("name", "layer group");',
        f'set("x", 0);  set("y", 0);  set("z", {um(z_bottom)});   # origin = bottom of the stack',
        f"loadgdsfile({q(gds_name)});",
        '?"GDS cells:"; ?getcelllist;',
        "cell_ok = 0;",
        f'try {{ set("gds cell", {q(cell)}); cell_ok = 1; }} catch(err_c1);',
        f'if (cell_ok == 0) {{ try {{ set("cell", {q(cell)}); cell_ok = 1; }} catch(err_c2); }}',
        f'if (cell_ok == 0) {{ ?"NOTE: select cell {cell} in the Layer Builder GDS drop-down by hand."; }}',
        "",
        "function lb_set(lname, prop, val) {",
        "    ok = 0;",
        "    try { setlayer(lname, prop, val); ok = 1; } catch(err_lb);",
        '    if (ok == 0) { ?"  could not set \'" + prop + "\' on " + lname; }',
        "    return ok;",
        "}",
        "",
    ]
    for s in slices:
        L += [
            f"addlayer({q(s.name)});",
            f'lb_set({q(s.name)}, "thickness", {um(s.z1 - s.z0)});',
        ]
        if multi:
            L.append(f'lb_set({q(s.name)}, "start position", {um(s.z0 - z_bottom)});')
        if s.background:
            L.append(
                f'lb_set({q(s.name)}, "background material", {q(process.material_name(s.background, "optical"))});'
            )
        if s.pattern:
            L += [
                f'try {{ setlayer({q(s.name)}, "process", "Grow"); }} catch(err_pg);',
                f'lb_set({q(s.name)}, "layer number", {q(s.expression)});',  # type: ignore[arg-type]
                f'lb_set({q(s.name)}, "pattern material", {q(process.material_name(s.pattern, "optical"))});',
            ]
        else:
            L.append(f'try {{ setlayer({q(s.name)}, "process", "Background"); }} catch(err_pb);')
        L.append("")
    L += [
        "sv_ok = 0;",
        f'try {{ saveprocessfile({q(lbr)}, {{"export materials": true}}); sv_ok = 1; }} catch(err_s1);',
        f"if (sv_ok == 0) {{ try {{ saveprocessfile({q(lbr)}); sv_ok = 1; }} catch(err_s2); }}",
        f'if (sv_ok == 1) {{ ?"Process file written: {lbr}"; }} else {{ ?"saveprocessfile failed -- export it from the Layer Builder GUI."; }}',
    ]
    return text + "\n".join(L) + "\n"
