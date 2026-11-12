"""2D cross-section scripts: layout cut -> CHARGE (carriers) -> MODE FDE (neff vs V).

Both scripts use the *same* frame -- x along the cut (0 at the waveguide centre),
z vertical, y = propagation -- so the carrier file written by CHARGE drops straight
into the FDE "np density" grid attribute without any rotation:

    CHARGE  "2D Y-Normal" simulation region  ->  <cell>_charge.mat  (n, p vs V_anode)
    FDE     "2D Y normal" solver             <-  importdataset(<cell>_charge.mat)

The CHARGE set-up (materials, contacts, solver, monitors) follows the Ansys
"PN depletion phase shifter" / "Ring Modulator" examples.
"""

from __future__ import annotations

from photonics_cookbook.lumerical.cutline import CrossSection2D, Interval
from photonics_cookbook.lumerical.lsf import ASCII_PATH_NOTE, header, ident, num, q, um
from photonics_cookbook.process import Process

JUNCTION_TOL = 0.02  # um


def junctions(xsec: CrossSection2D, process: Process) -> list[float]:
    """x positions where an n-type and a p-type implant interval meet (or overlap)."""
    dop = [(iv, process.layer(iv.role).dopant) for iv in xsec.intervals if process.layer(iv.role).kind == "doping"]
    xs: list[float] = []
    for a, ta in dop:
        for b, tb in dop:
            if ta == "n" and tb == "p":
                for xa in (a.x0, a.x1):
                    for xb in (b.x0, b.x1):
                        if abs(xa - xb) < JUNCTION_TOL:
                            xs.append(0.5 * (xa + xb))
    return sorted({round(x, 3) for x in xs})


def _contact_of(via: Interval, xsec: CrossSection2D, process: Process, anode_role: str, cathode_role: str) -> str | None:
    for iv in xsec.intervals:
        if iv.overlaps(via) and iv.role in (anode_role, cathode_role):
            return "anode" if iv.role == anode_role else "cathode"
    return None


CHARGE_HELPERS = r"""
###############################################################################
# 0. Helper functions
###############################################################################
function set_prio(mo) {
    try { set("override mesh order from material database", 1); } catch(e_mo1);
    try { set("mesh order", mo); } catch(e_mo2);
    return mo;
}
function add_rect(name, mat, x0, x1, z0, z1, mo) {
    addrect;
    set("name", name);
    set("material", mat);
    set("x", 0.5*(x0+x1));  set("x span", x1-x0);
    set("y", 0);            set("y span", 1e-6);
    set("z", 0.5*(z0+z1));  set("z span", z1-z0);
    set_prio(mo);
    return 1;
}
function add_dope_box(name, dtype, conc_cm3, x0, x1, z0, z1) {
    # constant (box) doping; concentration in cm^-3, CHARGE wants m^-3
    adddope;
    set("name", name);
    set("dopant type", dtype);
    set("concentration", conc_cm3*1e6);
    set("x", 0.5*(x0+x1));  set("x span", x1-x0);
    set("y", 0);            set("y span", 1e-6);
    set("z", 0.5*(z0+z1));  set("z span", z1-z0);
    return 1;
}
function add_mesh_box(name, edge, x0, x1, z0, z1) {
    addchargemesh;
    set("name", name);
    set("max edge length", edge);
    set("x", 0.5*(x0+x1));  set("x span", x1-x0);
    set("y", 0);            set("y span", 1e-6);
    set("z", 0.5*(z0+z1));  set("z span", z1-z0);
    return 1;
}
function try_set(objs, props, val) {
    # set the first (object, property) spelling that exists; returns it or ""
    # (flag + single return: no early return from inside loops)
    used = "";
    for (io = 1:length(objs)) {
        for (ip = 1:length(props)) {
            if (length(used) == 0) {
                e_ts = "";
                try { setnamed(objs{io}, props{ip}, val); } catch(e_ts);
                if (length(e_ts) == 0) { used = objs{io} + " : " + props{ip}; }
            }
        }
    }
    return used;
}
function add_ct_material(name, candidates) {
    addmodelmaterial;
    set("name", name);
    used = "";
    for (ic = 1:length(candidates)) {
        if (length(used) == 0) {
            e_ct = "";
            try { select("materials::" + name); } catch(e_sel);
            try { addmaterialproperties("CT", candidates{ic}); } catch(e_ct);
            if (length(e_ct) == 0) { used = candidates{ic}; }
        }
    }
    if (length(used) == 0) {
        ?"WARNING: no CT database entry found for " + name + " -- fix the 'charge' name in the process YAML.";
        try { ?addmaterialproperties("CT"); } catch(e_list);
    }
    return used;
}
"""


def charge2d_lsf(
    xsec: CrossSection2D,
    process: Process,
    norm_length_um: float,
    anode_role: str = "ppp",
    cathode_role: str = "npp",
    v_start: float = 0.0,
    v_stop: float = -4.0,
    n_points: int = 9,
    out_prefix: str | None = None,
    include_metal: bool = False,
    run: bool = True,
) -> str:
    """CHARGE 2D (y-normal) script for the cut ``xsec``. Anode swept, cathode grounded."""
    pre = out_prefix or ident(xsec.cell)
    si_top = process.si_top
    vias = [iv for iv in xsec.intervals if process.layer(iv.role).kind == "via"]
    if not vias:
        raise ValueError("the cut crosses no via -- CHARGE needs contacts; move the cut line")
    contacts: list[tuple[Interval, str]] = []
    for v in vias:
        c = _contact_of(v, xsec, process, anode_role, cathode_role)
        if c:
            contacts.append((v, c))
    kinds = {c for _, c in contacts}
    if kinds != {"anode", "cathode"}:
        raise ValueError(
            f"need one via on {anode_role!r} (anode) and one on {cathode_role!r} (cathode) along the cut; "
            f"found {sorted(kinds)}"
        )
    boxes = xsec.solid_boxes(process)
    z_top = max([z1 for iv, (z0, z1) in boxes if process.layer(iv.role).kind == "via"] + [si_top + 0.3])
    z_bot = -0.5
    xj = junctions(xsec, process)

    text = header(
        f"CHARGE 2D cross-section: {xsec.cell}",
        [
            f"Process : {process.name}  ({process.foundry})",
            f"Cut     : {xsec.p0} -> {xsec.p1} um, x = 0 at {xsec.origin}",
            f"Contacts: anode = via on {anode_role}, cathode = via on {cathode_role} (grounded)",
            f"Sweep   : V_anode {v_start} -> {v_stop} V ({n_points} pts); negative = reverse bias",
            f"Output  : {pre}_charge.ldev, {pre}_charge.mat (n, p for MODE FDE), {pre}_iv.mat",
            "Use     : Lumerical Finite Element IDE (CHARGE) -> run this script.",
            ASCII_PATH_NOTE,
        ],
    )
    L = [
        "newproject;",
        "redrawoff;",
        "try { cd(filedirectory(currentscriptname)); } catch(err_cd);",
        "um = 1e-6;  nm = 1e-9;",
        f"do_run      = {1 if run else 0};",
        f"V_start     = {num(v_start)};",
        f"V_stop      = {num(v_stop)};",
        f"N_V         = {int(n_points)};",
        f"norm_length = {um(norm_length_um)};   # device length the 2D results are scaled to",
        CHARGE_HELPERS,
        "###############################################################################",
        "# 1. Materials (electrical 'CT' properties)",
        "###############################################################################",
    ]
    used = {process.layer(iv.role).material for iv, _ in boxes} | {b.material for b in process.background}
    used.discard(None)
    for key in sorted(used):  # type: ignore[arg-type]
        mat = process.material(key)
        cands = [mat.name_for("charge")]
        if mat.kind == "conductor":
            cands += ["Al (Aluminium) - CRC", "Al (Aluminium)"]
        cands_l = "{" + ", ".join(q(c) for c in dict.fromkeys(cands)) + "}"
        L.append(f"add_ct_material({q(key)}, {cands_l});")
    semis = [k for k in sorted(used) if process.material(k).kind == "semiconductor"]  # type: ignore[arg-type]
    if semis:
        objs = "{" + ", ".join(f'"materials::{k}", "{k}"' for k in semis) + "}"
        L += [
            "",
            "# Physics models as in the Ansys PN-phase-shifter example: high-field (velocity",
            "# saturation) mobility is OFF in the database default -> switch it on.",
            "# Property paths differ between versions; the first one that works is used.",
            f'hf = try_set({objs}, {{"electronic.l.mun.high field.active model", "electronic.gamma.mun.high field.active model"}}, "monotonic");',
            f'try_set({objs}, {{"electronic.l.mup.high field.active model", "electronic.gamma.mup.high field.active model"}}, "monotonic");',
            f'try_set({objs}, {{"electronic.l.mun.high field.driving field", "electronic.gamma.mun.high field.driving field"}}, "grad Phi");',
            f'try_set({objs}, {{"electronic.l.mup.high field.driving field", "electronic.gamma.mup.high field.driving field"}}, "grad Phi");',
            'if (hf == "") { ?"NOTE: high-field mobility not set by script (check material tree)."; } else { ?"high-field mobility: " + hf; }',
        ]

    x0, x1 = xsec.x_min, xsec.x_max
    L += [
        "",
        "###############################################################################",
        "# 2. Geometry from the layout cut  (x along the cut, z from the process)",
        "###############################################################################",
    ]
    for b in process.background:
        if b.zmax <= z_bot:
            continue  # e.g. the Si handle far below the device layer
        L.append(
            f"add_rect({q(ident(b.name))}, {q(b.material)}, {um(x0 - 0.5)}, {um(x1 + 0.5)}, "
            f"{um(max(b.zmin, z_bot - 0.5))}, {um(b.zmax)}, 4);"
        )
    counters: dict[str, int] = {}
    contact_obj: dict[str, list[str]] = {"anode": [], "cathode": []}
    for iv, (z0, z1) in boxes:
        lay = process.layer(iv.role)
        if lay.kind == "metal" and not include_metal:
            continue
        counters[iv.role] = counters.get(iv.role, 0) + 1
        name = f"{iv.role}_{counters[iv.role]}"
        if lay.kind == "via":
            c = _contact_of(iv, xsec, process, anode_role, cathode_role)
            if c:
                name = f"{c}_via_{len(contact_obj[c]) + 1}"
                contact_obj[c].append(name)
        mo = 1 if lay.kind in ("via", "metal") else 2
        L.append(f"add_rect({q(name)}, {q(lay.material)}, {um(iv.x0)}, {um(iv.x1)}, {um(z0)}, {um(z1)}, {mo});")
    for iv in xsec.intervals:
        lay = process.layer(iv.role)
        if lay.kind == "etch":
            L.append(
                f"add_rect({q(ident(iv.role))}, {q(lay.material)}, {um(iv.x0)}, {um(iv.x1)}, "
                f"{um(si_top - lay.depth)}, {um(si_top)}, 1);"
            )

    L += [
        "",
        "###############################################################################",
        "# 3. Doping: one box per implant interval over the full Si thickness",
        "#    (CHARGE adds overlapping implants, as in the real process)",
        "###############################################################################",
    ]
    k = 0
    for iv in xsec.intervals:
        lay = process.layer(iv.role)
        if lay.kind != "doping":
            continue
        k += 1
        L.append(
            f"add_dope_box({q(f'{iv.role}_{k}')}, {q(lay.dopant)}, {num(lay.concentration)}, "
            f"{um(iv.x0)}, {um(iv.x1)}, 0, {um(si_top)});"
        )

    L += [
        "",
        "###############################################################################",
        "# 4. Simulation region, solver, mesh",
        "###############################################################################",
        "addsimulationregion;",
        'set("name", "sim_region");',
        "dim_ok = 0;",
        'try { set("dimension", "2D Y-Normal"); dim_ok = 1; } catch(err_dim);',
        'if (dim_ok == 0) { set("dimension", 2); }',
        f'set("x", {um(0.5 * (x0 + x1))});  set("x span", {um(x1 - x0)});',
        'set("y", 0);',
        f'set("z", {um(0.5 * (z_bot + z_top))});  set("z span", {um(z_top - z_bot)});',
        "",
        "addchargesolver;",
        "reg_ok = 0;",
        'try { set("simulation region", "sim_region"); reg_ok = 1; } catch(err_reg);',
        "if (reg_ok == 0) {",
        "    # newer releases: the solver carries its own geometry",
        '    ?"NOTE: no separate simulation region -- setting the geometry on the CHARGE solver.";',
        '    try { set("solver geometry", 1); } catch(err_sg);',
        '    try { set("dimension", "2D Y-Normal"); } catch(err_sd);',
        f'    try {{ set("x", {um(0.5 * (x0 + x1))}); set("x span", {um(x1 - x0)}); }} catch(err_sx);',
        f'    try {{ set("z", {um(0.5 * (z_bot + z_top))}); set("z span", {um(z_top - z_bot)}); }} catch(err_sz);',
        "}",
        'try { set("solver mode", "steady state"); } catch(err_sm);',
        'set("norm length", norm_length);',
        'try { set("min edge length", 0.5*nm); set("max edge length", 50*nm); } catch(err_el);',
        'try { set("temperature dependence", "isothermal"); } catch(err_s1);',
        'try { set("simulation temperature", 300); } catch(err_s2);',
        "",
    ]
    cores = [iv for iv in xsec.intervals if iv.role == "core"]
    for i, c in enumerate(cores, 1):
        L.append(f'add_mesh_box("mesh_core_{i}", 5*nm, {um(c.x0 - 0.1)}, {um(c.x1 + 0.1)}, 0, {um(si_top)});')
    for i, xj_ in enumerate(xj, 1):
        L.append(f'add_mesh_box("mesh_junction_{i}", 2*nm, {um(xj_ - 0.08)}, {um(xj_ + 0.08)}, 0, {um(si_top)});')
    si_iv = [iv for iv, _ in boxes if process.layer(iv.role).kind == "structure"]
    if si_iv:
        L.append(
            f'add_mesh_box("mesh_si", 20*nm, {um(min(i.x0 for i in si_iv))}, {um(max(i.x1 for i in si_iv))}, 0, {um(si_top)});'
        )

    L += [
        "",
        "###############################################################################",
        "# 5. Electrical contacts (vias found on the P++ / N++ intervals of the cut)",
        "###############################################################################",
    ]
    for c, objs in contact_obj.items():
        for i, obj in enumerate(objs, 1):
            cname = c if i == 1 else f"{c}{i}"
            L += [
                "addelectricalcontact;",
                f'set("name", {q(cname)});',
                'set("bc mode", "steady state");',
            ]
            if c == "anode":
                L += [
                    'set("sweep type", "range");',
                    'set("range start", V_start);',
                    'set("range stop", V_stop);',
                    'set("range num points", N_V);',
                ]
            else:
                L += ['set("sweep type", "single");', 'set("voltage", 0);']
            L += ['set("surface type", "solid");', f'set("solid", {q(obj)});', ""]

    si_x0 = min(i.x0 for i in si_iv) if si_iv else x0
    si_x1 = max(i.x1 for i in si_iv) if si_iv else x1
    L += [
        "###############################################################################",
        "# 6. Monitor: carrier densities saved for MODE (np density grid attribute)",
        "###############################################################################",
        "addchargemonitor;",
        'set("name", "charge");',
        'set("monitor type", 6);   # 2D y-normal',
        f'set("x", {um(0.5 * (x0 + x1))});  set("x span", {um(x1 - x0)});',
        'set("y", 0);',
        f'set("z", {um(si_top / 2)});  set("z span", {um(si_top + 0.02)});',
        'set("save data", 1);',
        f'set("filename", {q(pre + "_charge.mat")});',
        "",
        f"save({q(pre + '_charge.ldev')});",
        "",
        "if (do_run == 1) {",
        "    run;",
        '    iv = getresult("CHARGE", "anode");',
        "    V = pinch(iv.V_anode);",
        "    I = pinch(iv.I);",
        '    plot(V, abs(I), "V_anode (V)", "|I| (A)", "I-V of the device (norm length applied)");',
        f"    matlabsave({q(pre + '_iv.mat')}, V, I);",
        f'    ?"Done: {pre}_charge.mat written. Next: run {pre}_fde2d.lsf in MODE (same folder).";',
        "}",
        "redrawon;",
    ]
    # silicon extent comment (helps when reading the script)
    L.insert(0, f"# silicon spans x = {si_x0:.3f} .. {si_x1:.3f} um along the cut; junction(s) at {xj} um")
    return text + "\n".join(L) + "\n"


FDE_HELPERS = r"""
function add_rect(name, mat, x0, x1, z0, z1, mo, ga) {
    addrect;
    set("name", name);
    set("material", mat);
    set("x", 0.5*(x0+x1));  set("x span", x1-x0);
    set("y", 0);            set("y span", 1e-6);
    set("z", 0.5*(z0+z1));  set("z span", z1-z0);
    set("override mesh order from material database", 1);
    set("mesh order", mo);
    if (ga != "") { set("grid attribute name", ga); }
    return 1;
}
function pick_mode(nmodes, xc0, xc1) {
    # quasi-TE mode with the largest |E|^2 fraction inside the core window
    best = 1; bestscore = -1; bestxc = 0;
    for (m = 1:nmodes) {
        dc  = "FDE::data::mode" + num2str(m);
        x   = getdata(dc, "x");   z = getdata(dc, "z");
        Ex2 = pinch(abs(getdata(dc, "Ex"))^2);
        Ez2 = pinch(abs(getdata(dc, "Ez"))^2);
        E2  = Ex2 + pinch(abs(getdata(dc, "Ey"))^2) + Ez2;
        X   = meshgridx(x, z);
        msk = (X >= xc0) * (X <= xc1);
        fr  = integrate2(E2*msk, 1:2, x, z) / integrate2(E2, 1:2, x, z);
        te  = integrate2(Ex2, 1:2, x, z) / integrate2(Ex2 + Ez2, 1:2, x, z);
        score = fr * (te > 0.5);
        if (score > bestscore) {
            best = m;  bestscore = score;
            bestxc = integrate2(E2*msk*X, 1:2, x, z) / integrate2(E2*msk, 1:2, x, z);
        }
    }
    return [best, bestscore, bestxc];
}
"""


def fde2d_lsf(
    xsec: CrossSection2D,
    process: Process,
    bend_radius_um: float | None = None,
    bend_center_side: str = "-x",
    doped_length_um: float | None = None,
    ring_length_um: float | None = None,
    wavelength_um: float | None = None,
    charge_file: str | None = None,
    out_prefix: str | None = None,
    pml_margin: float = 0.3,
) -> str:
    """MODE FDE (2D Y normal) on the same cut; imports the CHARGE carrier file if present."""
    pre = out_prefix or ident(xsec.cell)
    cfile = charge_file or f"{pre}_charge.mat"
    lam = wavelength_um or process.wavelength_um
    si_top = process.si_top
    cores = [iv for iv in xsec.intervals if iv.role == "core"]
    if not cores:
        raise ValueError("the cut crosses no core layer")
    core = min(cores, key=lambda c: abs(0.5 * (c.x0 + c.x1)))
    half = min(-xsec.x_min, xsec.x_max) - pml_margin  # symmetric about x = 0 (bend centre)
    if half <= core.x1:
        raise ValueError("cut too short around the waveguide for an FDE region")
    orient = 90 if bend_center_side == "-x" else 270
    L_dop = doped_length_um
    L_ring = ring_length_um or (2 * 3.141592653589793 * bend_radius_um if bend_radius_um else None)

    text = header(
        f"MODE FDE 2D cross-section: {xsec.cell}",
        [
            f"Process : {process.name}  ({process.foundry})",
            f"Cut     : same frame as {pre}_charge2d.lsf (x along cut, 0 = waveguide centre)",
            f"Input   : {cfile} from CHARGE (optional -- without it: passive mode only)",
            f"Bend    : R = {bend_radius_um} um, centre towards {bend_center_side} (auto-checked)",
            f"Output  : {pre}_fde.lms, {pre}_fde_results.mat",
            "Use     : Lumerical MODE -> run this script.",
            ASCII_PATH_NOTE,
        ],
    )
    L = [
        "newproject;",
        "redrawoff;",
        "try { cd(filedirectory(currentscriptname)); } catch(err_cd);",
        "um = 1e-6;  nm = 1e-9;",
        f"lambda0     = {um(lam)};",
        f"bend_radius = {um(bend_radius_um) if bend_radius_um else 0};",
        f"bend_orient = {orient};   # 2D Y normal: 90 -> bend centre at -x, 270 -> at +x",
        f"L_doped     = {um(L_dop) if L_dop else 0};",
        f"L_ring      = {um(L_ring) if L_ring else 0};",
        f"charge_file = {q(cfile)};",
        "use_np      = fileexists(charge_file);",
        FDE_HELPERS,
        "###############################################################################",
        "# 1. Materials: Si with free-carrier (Soref-Bennett) perturbation if CHARGE data exist",
        "###############################################################################",
        f"mat_si = {q(process.material_name(process.layer('core').material, 'optical'))};",  # type: ignore[arg-type]
        'ga = "";',
        "if (use_np == 1) {",
        '    tmp = addmaterial("Index perturbation");',
        '    setmaterial(tmp, "name", "Si_np");',
        "    b_ok = 0;",
        '    try { setmaterial("Si_np", "base material", mat_si); b_ok = 1; } catch(err_b);',
        '    if (b_ok == 0) { ?"WARNING: could not set the base material of Si_np -- set it in the material editor. Properties:"; ?setmaterial("Si_np"); }',
        '    np_ok = 0;',
        '    try { setmaterial("Si_np", "np density model", "Soref and Bennet"); np_ok = 1; } catch(err_np);',
        '    if (np_ok == 0) { try { setmaterial("Si_np", "np density model", 1); } catch(err_np2); }',
        '    addgridattribute("np density");',
        '    set("name", "np_density");',
        "    importdataset(charge_file);",
        '    mat_si = "Si_np";',
        '    ga = "np_density";',
        "} else {",
        '    ?"No " + charge_file + " -> passive mode solve only (run the CHARGE script first for V-dependence).";',
        "}",
        "",
        "###############################################################################",
        "# 2. Geometry from the layout cut",
        "###############################################################################",
    ]
    big = half + 3.0
    for b in process.background:
        if b.zmax <= -1.5:
            continue
        mat = process.material(b.material)
        L.append(
            f"add_rect({q(ident(b.name))}, {q(mat.name_for('optical'))}, {um(-big)}, {um(big)}, "
            f"{um(max(b.zmin, -2.0))}, {um(b.zmax)}, {max(mat.mesh_order, 3)}, \"\");"
        )
    n_si = 0
    for iv in xsec.intervals:
        lay = process.layer(iv.role)
        if lay.kind != "structure":
            continue
        n_si += 1
        a = iv.x0 if iv.x0 > xsec.x_min + 1e-6 else -big  # run through the PML if cut there
        b = iv.x1 if iv.x1 < xsec.x_max - 1e-6 else big
        if lay.material == process.layer("core").material:
            L.append(f"add_rect({q(f'{iv.role}_{n_si}')}, mat_si, {um(a)}, {um(b)}, {um(lay.zmin)}, {um(lay.zmax)}, 2, ga);")
        else:
            mname = process.material_name(lay.material, "optical")  # type: ignore[arg-type]
            L.append(f'add_rect({q(f"{iv.role}_{n_si}")}, {q(mname)}, {um(a)}, {um(b)}, {um(lay.zmin)}, {um(lay.zmax)}, 2, "");')
    for iv in xsec.intervals:
        lay = process.layer(iv.role)
        if lay.kind == "etch":
            mname = process.material_name(lay.material, "optical")  # type: ignore[arg-type]
            L.append(
                f'add_rect({q(ident(iv.role))}, {q(mname)}, {um(iv.x0)}, {um(iv.x1)}, '
                f'{um(si_top - lay.depth)}, {um(si_top)}, 1, "");'
            )
    L += [
        "",
        "###############################################################################",
        "# 3. FDE solver (2D Y normal, x = lateral, z = vertical)",
        "###############################################################################",
        "addfde;",
        'set("solver type", "2D Y normal");',
        f'set("x", 0);  set("x span", {um(2 * half)});',
        'set("y", 0);',
        f'set("z", {um(si_top / 2)});  set("z span", {um(si_top + 2.0)});',
        'set("x min bc", "PML");  set("x max bc", "PML");',
        'set("z min bc", "PML");  set("z max bc", "PML");',
        'set("define x mesh by", "maximum mesh step");  set("dx", 20*nm);',
        'set("define z mesh by", "maximum mesh step");  set("dz", 20*nm);',
        "addmesh;",
        'set("name", "mesh_core");',
        f'set("x", {um(0.5 * (core.x0 + core.x1))});  set("x span", {um(core.x1 - core.x0 + 0.4)});',
        'set("y", 0);  set("y span", 1e-6);',
        f'set("z", {um(si_top / 2)});  set("z span", {um(si_top + 0.1)});',
        'set("override x mesh", 1);  set("override y mesh", 0);  set("override z mesh", 1);',
        'set("dx", 10*nm);  set("dz", 10*nm);',
        "",
        'setanalysis("wavelength", lambda0);',
        'setanalysis("number of trial modes", 8);',
        'setanalysis("search", "max index");',
        'ng_ok = 0;  try { setanalysis("calculate group index", 1); ng_ok = 1; } catch(err_ng);',
        f"xc0 = {um(core.x0)};  xc1 = {um(core.x1)};",
        f"save({q(pre + '_fde.lms')});",
        "",
        "###############################################################################",
        "# 4. Straight reference, then bend with automatic orientation check",
        "###############################################################################",
        "if (use_np == 1) { setnamed(\"np_density\", \"V_anode_index\", 1); }",
        'setanalysis("bent waveguide", 0);',
        "nm0 = findmodes;",
        "pk0 = pick_mode(nm0, xc0, xc1);",
        "xc_straight = pk0(3);",
        'neff_straight = real(getdata("FDE::data::mode" + num2str(pk0(1)), "neff"));',
        "if (bend_radius > 0) {",
        '    setanalysis("bent waveguide", 1);',
        '    setanalysis("bend radius", bend_radius);',
        '    try { setanalysis("bend location", "simulation center"); } catch(err_bl);',
        '    setanalysis("bend orientation", bend_orient);',
        "    nmd = findmodes;",
        "    pk = pick_mode(nmd, xc0, xc1);",
        f"    expect_plus = {1 if bend_center_side == '-x' else 0};   # mode must move away from the centre",
        "    moved_plus = pk(3) > xc_straight;",
        "    if (moved_plus != expect_plus) {",
        "        if (bend_orient == 90) { bend_orient = 270; } else { bend_orient = 90; }",
        '        setanalysis("bend orientation", bend_orient);',
        '        ?"bend orientation flipped to " + num2str(bend_orient);',
        "    }",
        "}",
        "",
        "###############################################################################",
        "# 5. Bias sweep (one mode solve per CHARGE bias point)",
        "###############################################################################",
        "V = 0;",
        "if (use_np == 1) { matlabload(charge_file); V = pinch(charge.V_anode); }",
        "nV = length(V);",
        "neff = matrix(nV);  loss_dBcm = matrix(nV);  ng = matrix(nV);",
        "for (i = 1:nV) {",
        "    switchtolayout;",
        '    if (use_np == 1) { setnamed("np_density", "V_anode_index", i); }',
        "    nmd = findmodes;",
        "    pk  = pick_mode(nmd, xc0, xc1);",
        '    dc  = "FDE::data::mode" + num2str(pk(1));',
        '    neff(i) = real(getdata(dc, "neff"));',
        '    loss_dBcm(i) = getdata(dc, "loss")/100;',
        '    if (ng_ok == 1) { try { ng(i) = real(getdata(dc, "ng")); } catch(err_g); }',
        '    ?"V = " + num2str(V(i)) + " V : neff = " + num2str(neff(i)) + " , loss = " + num2str(loss_dBcm(i)) + " dB/cm";',
        "}",
        "dneff = neff - neff(1);",
        "if (nV > 1) {",
        "    VpiL_cm = matrix(nV);",
        "    for (i = 2:nV) { if (abs(dneff(i)) > 0) { VpiL_cm(i) = lambda0*abs(V(i) - V(1))/(2*abs(dneff(i)))*100; } }",
        '    plot(V, dneff, "V_anode (V)", "delta n_eff", "index change vs bias");',
        '    plot(V, loss_dBcm, "V_anode (V)", "loss (dB/cm)", "mode loss vs bias");',
        "    if ((L_ring > 0) & (L_doped > 0) & (ng(1) > 0)) {",
        "        dlambda_pm = lambda0*dneff*(L_doped/L_ring)/ng(1)*1e12;",
        '        plot(V, dlambda_pm, "V_anode (V)", "resonance shift (pm)", "ring resonance shift");',
        '        ?"resonance tuning (first -> last bias): " + num2str((dlambda_pm(nV) - dlambda_pm(1))/(V(nV) - V(1))) + " pm/V";',
        "    }",
        f"    matlabsave({q(pre + '_fde_results.mat')}, V, neff, dneff, loss_dBcm, ng, VpiL_cm);",
        "} else {",
        f"    matlabsave({q(pre + '_fde_results.mat')}, neff, loss_dBcm, ng, neff_straight);",
        "}",
        "save;",
        "redrawon;",
    ]
    return text + "\n".join(L) + "\n"
