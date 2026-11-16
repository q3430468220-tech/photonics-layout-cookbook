"""Solver recipes that more than one device uses.  Each one was debugged once and is kept here.

    mode solver (FDE)   mesh lines on the silicon surfaces, reading a mode, telling guided modes from the rest
    EME                 set-up of the cell groups and ports, the length sweep
    FDTD                mode ports, a field monitor, running the engine, reading the S-parameters

Nothing here knows a device.  Lengths are in um; the functions convert to metres for Lumerical.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import numpy as np
from flow import LAM, LAM_MAX, LAM_MIN, T_SI, T_SLAB, import_lumapi, lumerical_root, um

# =====================================================================================
# mode solver (FDE)
# =====================================================================================
RIB_MARGIN = 0.3  # um: the slab mesh box runs this far beyond each core edge


def add_mesh_box(app, name: str, y0: float, y1: float, z0: float, z1: float, step: float,
                 x: tuple[float, float] = (-0.5, 0.5), dy: float | None = None) -> None:  # fmt: skip
    """A mesh override for a cross-section solver (normal to x), with its four faces at y0, y1, z0, z1.

    A mesh override forces a mesh line on each of its faces.  Put the faces on the silicon surfaces and the
    solver sees every interface exactly where the process file puts it.

    x: the range the box covers along the propagation direction (um).  A cross-section solver at x = 0 needs
    no more than the default; an EME or FDTD region needs its whole length.
    dy: mesh step in y if it differs from ``step``.
    """
    app.addmesh()
    app.set("name", name)
    app.set("x min", x[0] * um)
    app.set("x max", x[1] * um)
    app.set("y min", y0 * um)
    app.set("y max", y1 * um)
    app.set("z min", z0 * um)
    app.set("z max", z1 * um)
    app.set("override x mesh", 0)  # the structure is 2D in x: the x mesh of the solver is not used
    app.set("override y mesh", 1)
    app.set("override z mesh", 1)
    app.set("set maximum mesh step", 1)
    app.set("dy", (step if dy is None else dy) * um)
    app.set("dz", step * um)


def add_rib_mesh(app, width: float = 0.5, step: float = 0.01, y: float = 0.0) -> None:
    """Two mesh overrides that put a mesh line on every silicon surface of a rib centred on y (spans in um).

    Why: a uniform FDE mesh (20 nm here) has no line on the 90 nm slab surface or on the core sidewalls,
    unless a cell boundary happens to fall there, and which surfaces get one depends on where the window
    starts.  The same undoped rib bent to R = 10 um gave n_eff = 2.57648 in an 8 x 2.4 um window and 2.56932
    in a 3.4 x 1.9 um window.  With a line on every interface both windows agree: uniform 10 nm gives
    2.57102 in both, uniform 5 nm gives 2.57053 in both, and a 20 nm mesh with a 10 nm override over the rib
    gives 2.57016 and 2.57014.

        core mesh   |y| <= width / 2,            T_SLAB <= z <= T_SI   (core sidewalls, slab top, core top)
        slab mesh   |y| <= width / 2 + 0.3 um,   0 <= z <= T_SLAB      (slab edges beyond the core, slab bottom)

    The mesh inside them is ``step`` in y and z.  Call it after the solver object is added.
    """
    half = width / 2
    add_mesh_box(app, "core mesh", y - half, y + half, T_SLAB, T_SI, step)
    add_mesh_box(app, "slab mesh", y - half - RIB_MARGIN, y + half + RIB_MARGIN, 0.0, T_SLAB, step)


def add_strip_mesh(app, width: float = 0.5, step: float = 0.01, y: float = 0.0, name: str = "core mesh") -> None:
    """One mesh override with its faces on the four surfaces of a strip core centred on y (see add_rib_mesh)."""
    add_mesh_box(app, name, y - width / 2, y + width / 2, 0.0, T_SI, step)


def add_fde(app, y_span: float, z_span: float, mesh: float, y: float = 0.0, trial_modes: int = 8, guess: float = 2.6) -> None:
    """Mode solver on the plane x = 0, centred on the middle of the silicon layer, with PML on all four sides.

    The search is "near n": a search near the maximum index also returns slab modes and modes of the PML.
    Add the mesh overrides after this call: a new object takes the selection.
    """
    app.addfde()
    app.set("solver type", "2D X normal")
    app.set("x", 0)
    app.set("y", y * um)
    app.set("y span", y_span * um)
    app.set("z", T_SI / 2 * um)
    app.set("z span", z_span * um)
    for axis in ("y", "z"):
        app.set(f"define {axis} mesh by", "maximum mesh step")
        app.set(f"d{axis}", mesh * um)
    for bc in ("y min bc", "y max bc", "z min bc", "z max bc"):
        app.set(bc, "PML")
    app.setanalysis("wavelength", LAM * um)
    app.setanalysis("search", "near n")
    app.setanalysis("use max index", 0)
    app.setanalysis("n", guess)
    app.setanalysis("number of trial modes", trial_modes)
    app.setanalysis("calculate group index", 1)
    app.setanalysis("bend location", "simulation center")
    app.setanalysis("bend orientation", 0)


def index_map(app) -> dict:
    """The refractive index the mode solver sees on its plane: mesh the structure and read the material data.

    Returns y, z (um) and index[y, z].  It is the check that the Layer Builder built what the layout says.
    """
    app.mesh()
    return dict(
        y=np.squeeze(app.getdata("FDE::data::material", "y")) / um,
        z=np.squeeze(app.getdata("FDE::data::material", "z")) / um,
        index=np.real(np.squeeze(app.getdata("FDE::data::material", "index_y"))).astype(np.float32),
    )


def cell_areas(y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Area of each cell of a field map indexed [y, z]; np.gradient gives the cell widths of a non-uniform mesh."""
    return np.outer(np.gradient(y), np.gradient(z))


def mode_info(app, i: int, core: tuple[float, float] = (-0.6, 0.6)) -> dict:
    """One mode of the last findmodes: indices, loss, polarisation, where its power sits, and its intensity map.

    core: the range of y (um) counted as "in the waveguide" for ``core_fraction``.
    The mesh is not uniform, so every sum over the map is weighted by the cell areas.
    """
    d = f"FDE::data::mode{i}"
    intensity = sum(np.abs(np.squeeze(app.getdata(d, c))) ** 2 for c in ("Ex", "Ey", "Ez"))
    y, z = np.squeeze(app.getdata(d, "y")), np.squeeze(app.getdata(d, "z"))
    power = intensity * cell_areas(y, z)
    profile = power.sum(axis=1)  # power in each row of cells, against y
    inside = (y >= core[0] * um) & (y <= core[1] * um)
    info = dict(
        i=i,
        neff=complex(np.squeeze(app.getdata(d, "neff"))),
        te=float(np.squeeze(app.getdata(d, "TE polarization fraction"))),
        loss_dBcm=float(np.squeeze(app.getdata(d, "loss"))) / 100,  # the solver reports dB/m
        y_centre=float((profile * y).sum() / profile.sum()) / um,
        core_fraction=float(profile[inside].sum() / profile.sum()),
        E=intensity.astype(np.float32),
        y=y / um,
        z=z / um,
    )
    try:
        info["ng"] = float(np.real(np.squeeze(app.getdata(d, "ng"))))
    except Exception:
        info["ng"] = float("nan")
    return info


def guided_modes(app, core: tuple[float, float] = (-0.6, 0.6), n_min: float = 1.46, core_min: float = 0.3) -> list[dict]:
    """Run findmodes and keep the guided modes, highest n_eff first.

    A mode counts as guided when its index is above ``n_min`` (the oxide is 1.444; in a rib, pass the index
    of the slab mode instead) and at least ``core_min`` of its power lies in the ``core`` range of y.
    The filter matters: the solver also returns slab modes and modes that live in the PML.
    """
    modes = [mode_info(app, i, core) for i in range(1, int(app.findmodes()) + 1)]
    modes = [m for m in modes if m["neff"].real > n_min and m["core_fraction"] > core_min]
    return sorted(modes, key=lambda m: -m["neff"].real)


def pick(modes: list[dict], polarisation: str, order: int = 0) -> dict | None:
    """The mode of the given order among the TE (TE fraction > 0.5) or the TM modes of a list sorted by n_eff."""
    wanted = [m for m in modes if (m["te"] > 0.5) == (polarisation == "TE")]
    return wanted[order] if len(wanted) > order else None


def cell_overlap(a: dict, b: dict) -> float:
    """Intensity overlap of two mode maps, every cell weighted by its area: 1 for identical maps.

    The maps must sit on the same grid (same window and mesh); otherwise nan.
    """
    if a["E"].shape != b["E"].shape or not (np.allclose(a["y"], b["y"]) and np.allclose(a["z"], b["z"])):
        return float("nan")
    cell = cell_areas(a["y"], a["z"])
    ea, eb = a["E"].astype(float), b["E"].astype(float)
    cross = np.sum(np.sqrt(ea * eb) * cell) ** 2
    return float(cross / (np.sum(ea * cell) * np.sum(eb * cell)))


def bend_sweep(app, radii, straight: dict, polarisation: str = "TE", core: tuple[float, float] = (-0.6, 0.6),
               n_min: float = 1.46, orientation: float = 0.0) -> dict:  # fmt: skip
    """The fundamental mode of the waveguide bent to each radius (um), compared with its straight mode.

    straight: the mode_info of the straight waveguide; its d-card "straight" must exist (copydcard).
    For every radius the table holds: n_eff, n_g, the radiation loss in dB/cm and per 90 degree turn, the
    shift of the mode centre in nm (a bent mode moves outwards, away from the centre of the bend, so the
    sign of the shift tells on which side the outside is), and the power that passes a junction between the
    straight and the bent waveguide (the solver's overlap of the two modes).  A 90 degree bend between two
    straights loses  radiation + 2 junctions.

    The search starts at the straight n_eff and follows the mode from the largest radius down.
    The solver is left in the straight state.
    """
    keys = ("neff", "ng", "loss_dBcm", "radiation_dB_90", "shift_nm", "junction", "junction_dB", "bend_dB_90")
    table = {k: [] for k in keys}
    order = sorted(radii, reverse=True)
    guess = straight["neff"].real
    app.switchtolayout()
    app.setanalysis("bent waveguide", 1)
    app.setanalysis("bend orientation", orientation)
    rows = {}
    for radius in order:
        app.switchtolayout()
        app.setanalysis("bend radius", radius * um)
        app.setanalysis("n", guess)
        mode = pick(guided_modes(app, core, n_min), polarisation)
        if mode is None:
            rows[radius] = None
            continue
        guess = mode["neff"].real
        junction = float(np.ravel(np.squeeze(app.overlap("straight", f"FDE::data::mode{mode['i']}")))[1])
        radiation = mode["loss_dBcm"] * (np.pi / 2) * radius * 1e-4
        junction_dB = -10 * np.log10(junction)
        rows[radius] = dict(neff=mode["neff"].real, ng=mode["ng"], loss_dBcm=mode["loss_dBcm"], radiation_dB_90=radiation,
                            shift_nm=(mode["y_centre"] - straight["y_centre"]) * 1000, junction=junction,
                            junction_dB=junction_dB, bend_dB_90=radiation + 2 * junction_dB, mode=mode)  # fmt: skip
    for radius in sorted(radii):
        row = rows[radius]
        for k in keys:
            table[k].append(np.nan if row is None else row[k])
    app.switchtolayout()
    app.setanalysis("bent waveguide", 0)
    out = {k: np.array(v, float) for k, v in table.items()}
    out["radii"] = np.array(sorted(radii), float)
    out["modes"] = {radius: (None if row is None else row["mode"]) for radius, row in rows.items()}
    return out


def wavelength_sweep(app, wavelengths, polarisation: str = "TE", core: tuple[float, float] = (-0.6, 0.6),
                     n_min: float = 1.46, guess: float = 2.6) -> dict:  # fmt: skip
    """n_eff and n_g of the fundamental mode at each wavelength (um): one findmodes per wavelength.

    Lumerical's built-in frequency sweep tracks a mode by overlap and can jump to a PML mode; a search
    near the previous n_eff does not.  Also returns the group index from the slope of n_eff, by a
    quadratic fit over the sweep.  The solver is left at the design wavelength.
    """
    neff, ng = [], []
    for lam in wavelengths:
        app.switchtolayout()
        app.setanalysis("wavelength", lam * um)
        app.setanalysis("n", guess)
        mode = pick(guided_modes(app, core, n_min), polarisation)
        neff.append(mode["neff"].real if mode else np.nan)
        ng.append(mode["ng"] if mode else np.nan)
        if mode:
            guess = mode["neff"].real
    app.switchtolayout()
    app.setanalysis("wavelength", LAM * um)
    lam, neff, ng = np.array(wavelengths, float), np.array(neff), np.array(ng)
    fit = np.polyfit(lam, neff, 2)
    ng_fit = float(np.polyval(fit, LAM) - LAM * np.polyval(np.polyder(fit), LAM))
    return dict(lam=lam, neff=neff, ng=ng, ng_fit=ng_fit)


def slab_te0_index(thickness: float, wavelength: float, n_core: float, n_clad: float) -> float:
    """n_eff of the fundamental TE mode of a symmetric three-layer slab (lengths in um).

    It is the reference for a rib waveguide: a mode of the rib is guided sideways only while its index is
    above that of the slab beside the core.  With u^2 + w^2 = V^2 and u tan(u) = w, the mode is the root
    of u tan(u) - w in (0, V); found by bisection.
    """
    half = np.pi / wavelength * thickness
    v = half * np.sqrt(n_core**2 - n_clad**2)
    lo, hi = 1e-9, v * (1 - 1e-12)
    for _ in range(100):
        mid = (lo + hi) / 2
        if (lo * np.tan(lo) - np.sqrt(v * v - lo * lo)) * (mid * np.tan(mid) - np.sqrt(v * v - mid * mid)) <= 0:
            hi = mid
        else:
            lo = mid
    w = np.sqrt(v * v - ((lo + hi) / 2) ** 2)
    return float(np.sqrt(n_clad**2 + (w / half) ** 2))


def mode_table(named: dict[str, dict | None]) -> list[str]:
    """Lines of a table of modes: name -> mode_info, or None for a mode that is not guided."""
    lines = [f"{'mode':>6} {'n_eff':>9} {'n_g':>8} {'TE fraction':>12} {'in core region':>15} {'loss dB/cm':>11}"]
    for label, mode in named.items():
        if mode is None:
            lines.append(f"{label:>6}   not guided")
        else:
            lines.append(f"{label:>6} {mode['neff'].real:9.5f} {mode['ng']:8.4f} {mode['te']:12.3f} {mode['core_fraction']:15.3f} "
                         f"{mode['loss_dBcm']:11.2g}")  # fmt: skip
    return lines


def bend_table(bend: dict) -> list[str]:
    """Lines of the table of a bend_sweep."""
    lines = [f"{'R (um)':>7} {'n_eff':>9} {'radiation dB/cm':>16} {'radiation dB/90deg':>19} {'junction dB':>12} "
             f"{'bend dB/90deg':>14} {'mode shift nm':>14}"]  # fmt: skip
    for i, radius in enumerate(bend["radii"]):
        if np.isnan(bend["neff"][i]):
            lines.append(f"{radius:7.1f}   no guided mode")
            continue
        lines.append(f"{radius:7.1f} {bend['neff'][i]:9.5f} {bend['loss_dBcm'][i]:16.3g} {bend['radiation_dB_90'][i]:19.2g} "
                     f"{bend['junction_dB'][i]:12.4f} {bend['bend_dB_90'][i]:14.4f} {abs(bend['shift_nm'][i]):14.1f}")  # fmt: skip
    return lines


def cutoff_sentence(widths: np.ndarray, neff: np.ndarray, label: str) -> str:
    """One sentence on where a higher mode appears in a width sweep (nan in ``neff``: not found)."""
    found = ~np.isnan(neff)
    if found.all():
        return f"{label} is found at every width of the sweep"
    if not found.any():
        return f"{label} is not found at any width of the sweep"
    return (
        f"{label} appears between {widths[~found].max():.2f} and {widths[found].min():.2f} um: "
        f"the sweep finds one TE mode up to {widths[~found].max():.2f} um"
    )


# =====================================================================================
# EME (eigenmode expansion): long, slowly varying devices
# =====================================================================================
def add_eme(app, x_min: float, groups: list[tuple[float, int, bool]], y_span: float, z_span: float, mesh: float,
            modes: int, y: float = 0.0, y_symmetry: str | None = None) -> None:  # fmt: skip
    """EME solver that propagates along x from ``x_min``.

    groups: one (length in um, number of cells, cvcs) per cell group, from left to right.  A uniform
        section is one cell.  A section whose cross-section changes is cut into several cells, with
        ``cvcs=True``: the continuously-varying-cross-section method removes the staircase between cells.
    modes: the number of modes kept in every cell.  The answer must not change when it is raised.
    y_symmetry: "Anti-Symmetric" for a structure that is mirror-symmetric in y and fed with a TE mode
        (the official taper example does this); it halves the problem and leaves out the odd modes,
        which a symmetric device cannot excite.  None solves the whole cross-section.

    The other walls are metal, the EME default: the window must be wide enough that the modes of
    interest do not feel them.
    """
    app.addeme()
    app.set("x min", x_min * um)
    app.set("y", y * um)
    app.set("y span", y_span * um)
    app.set("z", T_SI / 2 * um)
    app.set("z span", z_span * um)
    app.set("wavelength", LAM * um)
    app.set("number of cell groups", len(groups))
    app.set("group spans", np.array([[g[0] * um] for g in groups]))
    app.set("cells", np.array([[g[1]] for g in groups]))
    app.set("subcell method", np.array([[1 if g[2] else 0] for g in groups]))
    app.set("number of modes for all cell groups", modes)
    for axis in ("y", "z"):
        app.set(f"define {axis} mesh by", "maximum mesh step")
        app.set(f"d{axis}", mesh * um)
    if y_symmetry is not None:
        app.set("y min bc", y_symmetry)


def run_eme(app) -> None:
    """Run the EME project and make sure it holds results afterwards.

    ``run`` can come back without having run.  It happened twice here, both times at the last run of
    taper_eme.py: no error, no new engine log, the project still in layout mode, and the next command
    failed with "emesweep cannot be used while in layout mode".  A second attempt ten seconds later ran
    normally.  The cause was not found; an FDTD run was busy on the same machine both times.  So the
    state is checked, the run is tried once more, and then the script stops with a message that says
    where to look.
    """
    for attempt in (1, 2):
        app.run()
        if int(app.layoutmode()) == 0:
            return
        if attempt == 1:
            print("the EME run came back in layout mode, without results; trying once more", flush=True)
            time.sleep(10)
    raise RuntimeError("the EME run came back twice without results: see the *_p0.log next to the project, and the licence")


def set_eme_port(app, name: str, side: str, y: float | None = None, y_span: float | None = None,
                 mode: str = "fundamental TE mode") -> None:  # fmt: skip
    """Place an EME port ("port_1" and "port_2" exist; add more with app.addemeport()).

    side: "left" or "right".  y, y_span (um): a port that covers one waveguide of several; the full
    cross-section otherwise.
    """
    port = f"EME::Ports::{name}"
    app.setnamed(port, "port location", side)
    if y is None:
        app.setnamed(port, "use full simulation span", 1)
    else:
        app.setnamed(port, "use full simulation span", 0)
        app.setnamed(port, "y", y * um)
        app.setnamed(port, "y span", y_span * um)
    app.setnamed(port, "mode selection", mode)


def eme_length_sweep(app, group: int, start: float, stop: float, points: int) -> dict:
    """Sweep the length of one cell group (um) after ``app.run()``; no mode is computed again.

    This is what EME is for: the modes of every cell are known, and a new length only changes the phase
    each mode collects.  Returns the lengths (um) and the complex S-matrix elements, as s21, s31, s11, ...
    """
    app.setemeanalysis("propagation sweep", 1)
    app.setemeanalysis("parameter", f"group span {group}")
    app.setemeanalysis("start", start * um)
    app.setemeanalysis("stop", stop * um)
    app.setemeanalysis("number of points", points)
    app.emesweep()
    data = app.getemesweep("S")
    out = {"length": np.squeeze(data[f"group_span_{group}"]) / um}
    out.update({k: np.squeeze(v) for k, v in data.items() if k.startswith("s") and k[1:].isdigit()})
    return out


def add_eme_profile(
    app, name: str, x0: float, x1: float, y_span: float, y: float = 0.0, z: float | None = None, points: int = 300
) -> None:
    """Field monitor of the EME on a horizontal plane (the middle of the silicon layer by default)."""
    app.addemeprofile()
    app.set("name", name)
    app.set("monitor type", "2D Z-normal")
    app.set("x min", x0 * um)
    app.set("x max", x1 * um)
    app.set("y", y * um)
    app.set("y span", y_span * um)
    app.set("z", (T_SI / 2 if z is None else z) * um)
    app.set("x resolution", points)  # samples along the propagation direction


def eme_profile(app, name: str) -> dict:
    """|E| on an EME profile monitor after ``app.emepropagate()``: x, y in um and E[x, y]."""
    data = app.getresult(name, "field profile")
    e = np.squeeze(data["E"])
    return dict(x=np.squeeze(data["x"]) / um, y=np.squeeze(data["y"]) / um, E=np.linalg.norm(e, axis=-1).astype(np.float32))


# =====================================================================================
# FDTD: short devices where the light changes direction or shape quickly
# =====================================================================================
PORT_Y_SPAN, PORT_Z_SPAN = 2.4, 1.6  # um: mode port around a single-mode waveguide
Z_FDTD = (-1.0, 1.0)  # um: inside the 2 um buried oxide and below metal 1


def add_fdtd(app, x: tuple[float, float], y: tuple[float, float], mesh_accuracy: int = 2, sim_time: float = 3e-12) -> None:
    """3D FDTD region from x[0] to x[1] and y[0] to y[1] (um), PML on every side, for the band of flow.py.

    The layout must reach beyond the region where a waveguide leaves it: the waveguide then runs into the
    PML and nothing reflects from its end.
    """
    app.addfdtd()
    app.set("dimension", "3D")
    app.set("x min", x[0] * um)
    app.set("x max", x[1] * um)
    app.set("y min", y[0] * um)
    app.set("y max", y[1] * um)
    app.set("z min", Z_FDTD[0] * um)
    app.set("z max", Z_FDTD[1] * um)
    app.set("mesh accuracy", mesh_accuracy)
    app.set("simulation time", sim_time)
    app.set("auto shutoff min", 1e-5)
    app.setglobalsource("wavelength start", LAM_MIN * um)
    app.setglobalsource("wavelength stop", LAM_MAX * um)


def add_fdtd_mesh(app, name: str, x: tuple[float, float], y: tuple[float, float], step: float) -> None:
    """Fine mesh over the part of the device that decides the answer (a gap, a multimode section).

    The box runs from the bottom to the top of the silicon, so there is a mesh line on both surfaces; the
    mesh is ``step`` in y and z, and left to the solver along x.
    """
    app.addmesh()
    app.set("name", name)
    app.set("x min", x[0] * um)
    app.set("x max", x[1] * um)
    app.set("y min", y[0] * um)
    app.set("y max", y[1] * um)
    app.set("z min", 0.0)
    app.set("z max", T_SI * um)
    app.set("override x mesh", 0)
    app.set("dy", step * um)
    app.set("dz", step * um)


def add_fdtd_port(app, name: str, x: float, y: float, direction: str, y_span: float = PORT_Y_SPAN) -> None:
    """Mode port on a waveguide along x.  direction: "Forward" for a port that injects towards +x, "Backward" otherwise."""
    app.addport()
    app.set("name", name)
    app.set("injection axis", "x-axis")
    app.set("direction", direction)
    app.set("x", x * um)
    app.set("y", y * um)
    app.set("y span", y_span * um)
    app.set("z", T_SI / 2 * um)
    app.set("z span", PORT_Z_SPAN * um)
    app.set("mode selection", "fundamental TE mode")


def set_fdtd_source(app, port: str, frequency_points: int = 101) -> None:
    app.select("FDTD::ports")
    app.set("source port", port)
    app.set("monitor frequency points", frequency_points)


def add_field_monitor(app, name: str, x: tuple[float, float], y: tuple[float, float]) -> None:
    """|E| on the plane through the middle of the silicon, at the design wavelength only."""
    app.addpower()
    app.set("name", name)
    app.set("monitor type", "2D Z-normal")
    app.set("x min", x[0] * um)
    app.set("x max", x[1] * um)
    app.set("y min", y[0] * um)
    app.set("y max", y[1] * um)
    app.set("z", T_SI / 2 * um)
    app.set("override global monitor settings", 1)
    app.set("use source limits", 0)
    app.set("frequency points", 1)
    app.set("wavelength center", LAM * um)
    for component in ("Hx", "Hy", "Hz", "Px", "Py", "Pz"):
        app.set(f"output {component}", 0)


def run_fdtd_engine(fsp: Path, threads: int, job_manager: bool = False) -> None:
    """Run a saved FDTD project.

    By default the CPU engine is started directly: on some machines the job manager picks a GPU resource
    or fails silently.  ``job_manager=True`` uses Lumerical's own resource configuration; it is also the
    fallback when the engine binary is not found.
    """
    engine = lumerical_root() / "bin" / ("fdtd-engine.exe" if os.name == "nt" else "fdtd-engine")
    if job_manager or not engine.exists():
        with import_lumapi().FDTD(filename=str(fsp), hide=True) as app:
            app.run()
            app.save(str(fsp))
        return
    log = fsp.with_name(fsp.stem + "_engine.out")
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.run(
            [str(engine), "-t", str(threads), str(fsp)], stdout=fh, stderr=subprocess.STDOUT, cwd=str(fsp.parent)
        )
    if proc.returncode != 0:
        tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:])
        raise RuntimeError(f"fdtd-engine exited with code {proc.returncode}, see {log}\n{tail}")
    log.unlink(missing_ok=True)


def solve_fdtd(fsp: Path, build, ports: list[str], field: str | None = None, threads: int = 8,
               job_manager: bool = False, keep_results: bool = False) -> dict:  # fmt: skip
    """Build a project with ``build(app)``, run it, and return what the ports and the field monitor recorded.

    Returns lam (um, ascending) and S1, S2, ...: the complex amplitude that leaves through each port for a
    unit amplitude from the source port.  With ``field``, also field_x, field_y (um) and field_E = |E|[x, y].
    The project is saved again without its fields afterwards (hundreds of MB otherwise), unless ``keep_results``.
    """
    lumapi = import_lumapi()
    with lumapi.FDTD(hide=True) as app:
        build(app)
        app.save(str(fsp))
    run_fdtd_engine(fsp, threads, job_manager)
    out: dict = {}
    with lumapi.FDTD(filename=str(fsp), hide=True) as app:
        if int(app.layoutmode()) == 1:
            raise RuntimeError(f"{fsp.name}: the engine finished but the file holds no results, see {fsp.stem}_p0.log")
        for port in ports:
            s = app.getresult(f"FDTD::ports::{port}", "S")
            lam = np.squeeze(s["lambda"]) / um
            order = np.argsort(lam)
            out["lam"] = lam[order]
            out[f"S{port[-1]}"] = np.squeeze(s["S"])[order]
        if field is not None:
            e = app.getresult(field, "E")
            out["field_x"] = np.squeeze(e["x"]) / um
            out["field_y"] = np.squeeze(e["y"]) / um
            out["field_E"] = np.linalg.norm(np.squeeze(e["E"]), axis=-1).astype(np.float32)
        if not keep_results:
            app.switchtolayout()
            app.save(str(fsp))
    return out


def at_wavelength(res: dict, wavelength: float = LAM) -> dict[str, float]:
    """|S|^2 of every port at one wavelength, interpolated linearly between the grid points."""
    lam = np.asarray(res["lam"], float)
    if not lam[0] <= wavelength <= lam[-1]:  # np.interp would clamp to the end point without a word
        raise ValueError(f"wavelength {wavelength} um is outside the simulated range {lam[0]:.4f} to {lam[-1]:.4f} um")
    return {
        key[1:]: float(np.interp(wavelength, lam, np.abs(np.asarray(res[key])) ** 2))
        for key in res
        if key[0] == "S" and key[1:].isdigit()
    }


def clean_logs(folder: Path) -> None:
    """Remove the solver logs of finished runs; the numbers that matter are in the .txt and .npz files."""
    for pattern in ("*_p0.log", "*_engine.out"):
        for path in folder.glob(pattern):
            path.unlink(missing_ok=True)


__all__ = [
    "LAM",
    "LAM_MAX",
    "LAM_MIN",
    "add_eme",
    "add_eme_profile",
    "add_fde",
    "add_fdtd",
    "add_fdtd_mesh",
    "add_fdtd_port",
    "add_field_monitor",
    "add_mesh_box",
    "add_rib_mesh",
    "add_strip_mesh",
    "at_wavelength",
    "bend_sweep",
    "bend_table",
    "cell_areas",
    "cell_overlap",
    "clean_logs",
    "cutoff_sentence",
    "eme_length_sweep",
    "eme_profile",
    "guided_modes",
    "import_lumapi",
    "index_map",
    "lumerical_root",
    "mode_info",
    "mode_table",
    "pick",
    "run_eme",
    "run_fdtd_engine",
    "set_eme_port",
    "set_fdtd_source",
    "slab_te0_index",
    "solve_fdtd",
]
