"""Step 3 - CHARGE: carriers in the PN section versus bias, junction capacitance and series resistance.

Model: a straight section of the PDK cross-section ``rib_1550nm_TE_pn`` with the via bands of
rm_builder, written to GDS and loaded into a Layer Builder with cornerstone_process.lbr.  All
doping comes from the process file.  The two via bands are separate solids there (via on P++,
via on N++), so each can carry its own contact:

    anode   = Via_P   (p side)          cathode = Via_N   (n side)
    V = V_anode - V_cathode;  negative = reverse bias = depletion

The simulation is a 2D cross-section normalised to the length of the doped arc, so currents,
capacitance and resistance are those of the whole PN section of the ring.

    1. steady state, anode 0 V -> V_min:  n(y, z, V), p(y, z, V)  -> .mat file for step 5
    2. small signal (ssac) at each bias:   C = Im(Y) / omega,  Rs = Re(1 / Y)  ->  f_RC = 1 / (2 pi Rs C)

    python charge_profile.py                      # 0 -> -4 V in 17 points
    python charge_profile.py --vmin -2 --points 9 --no-ssac

Output in 3_charge_profile/:  pn_rib.gds / .ldev, pn_rib_charge.mat, pn_rib_charge.npz / .txt
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from common import (
    L_PN,
    SLAB_WIDTH,
    T_SI,
    T_SLAB,
    WIDTH,
    add_layer_builder,
    import_lumapi,
    require_process_file,
    rm,
    section_gds,
    step_dir,
    strip,
    t,
    um,
)

OUT = step_dir("3_charge_profile")
NAME = "pn_rib"
LENGTH = 6.0  # um of waveguide in the GDS; the simulation is 2D
Y_SPAN = SLAB_WIDTH + 0.4
Z_MIN, Z_MAX = -0.5, 1.15  # inside the BOX and the top cladding; the vias pass through the top
JUNCTION_MESH = 0.008  # um, maximum edge length of the mesh over the rib


def write_gds():
    """PN section + via bands.  Along +x the cross-section has n on the left (+y) and p on the right (-y)."""

    def vias(c, x0, x1):
        for side in (+1, -1):
            y0, y1 = sorted((side * rm.VIA_GAP, side * (rm.VIA_GAP + rm.VIA_WIDTH)))
            c.add_polygon(strip(x0, x1, y0, y1), layer=t.VIA)

    xs = {"cross_section": "rib_1550nm_TE_pn", "settings": {"width": WIDTH, "width_slab": SLAB_WIDTH}}
    return section_gds(OUT / f"{NAME}.gds", xs, LENGTH, extra=vias)


def setup(d, gds) -> None:
    d.switchtolayout()  # no deleteall here: it would remove the materials group the process file fills
    add_layer_builder(d, gds, LENGTH, SLAB_WIDTH + 2.0)
    d.select("simulation region")  # a new DEVICE project already has one; use it
    d.set("dimension", "2D X-Normal")
    d.set("x", 0)
    d.set("y", 0)
    d.set("y span", Y_SPAN * um)
    d.set("z", (Z_MIN + Z_MAX) / 2 * um)
    d.set("z span", (Z_MAX - Z_MIN) * um)
    d.addchargesolver()
    d.select("CHARGE")
    d.set("norm length", L_PN * um)
    # A fine mesh over the rib: the capacitance comes from how far the depletion edge moves per volt.
    # With the automatic mesh alone, C(V) scatters by several percent from run to run.
    d.addchargemesh()
    d.set("name", "junction")
    d.set("x", 0)
    d.set("x span", LENGTH * um)
    d.set("y", 0)
    d.set("y span", (WIDTH + 0.5) * um)
    d.set("z", T_SI / 2 * um)
    d.set("z span", (T_SI + 0.02) * um)
    d.set("max edge length", JUNCTION_MESH * um)
    for name, solid in (("anode", "Via_P"), ("cathode", "Via_N")):
        d.addelectricalcontact()
        d.set("name", name)
        d.set("surface type", "solid")
        d.set("solid", solid)
        d.set("bc mode", "steady state")
        d.set("sweep type", "single")
        d.set("voltage", 0.0)
    d.addchargemonitor()
    d.set("name", "charge")
    d.set("monitor type", "2D x-normal")
    d.set("x", 0)
    d.set("y", 0)
    d.set("y span", Y_SPAN * um)
    d.set("z", (Z_MIN + Z_MAX) / 2 * um)
    d.set("z span", (Z_MAX - Z_MIN) * um)


def region_mean(y, z, elements, values, inside) -> float:
    """Area-weighted mean of a nodal quantity over the mesh triangles whose centroid satisfies ``inside(y, z)``."""
    tri = np.asarray(elements, dtype=int) - 1  # Lumerical numbers nodes from 1
    y0, y1, y2 = (y[tri[:, k]] for k in range(3))
    z0, z1, z2 = (z[tri[:, k]] for k in range(3))
    area = 0.5 * np.abs((y1 - y0) * (z2 - z0) - (y2 - y0) * (z1 - z0))
    selected = inside((y0 + y1 + y2) / 3, (z0 + z1 + z2) / 3)
    return float((values[tri].mean(axis=1) * area)[selected].sum() / area[selected].sum())


def junction_position(y, z, net) -> float:
    """y (um) where the net doping changes sign inside the core, at mid height of the rib."""
    sel = (np.abs(z - 0.16) < 0.03) & (np.abs(y) < WIDTH / 2)
    ys, ns = y[sel], net[sel]
    order = np.argsort(ys)
    ys, ns = ys[order], ns[order]
    flips = np.where(np.sign(ns[:-1]) != np.sign(ns[1:]))[0]
    return float((ys[flips[0]] + ys[flips[0] + 1]) / 2) if len(flips) else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vmin", type=float, default=-4.0, help="most negative anode voltage (V)")
    ap.add_argument("--points", type=int, default=17, help="bias points; keep the step at 0.25 V or below")
    ap.add_argument("--freqs", type=float, nargs="*", default=[1e8, 1e9, 1e10, 3e10], help="ssac frequencies (Hz)")
    ap.add_argument("--no-ssac", action="store_true")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    gds = write_gds()
    ldev, mat = OUT / f"{NAME}.ldev", OUT / f"{NAME}_charge.mat"
    res = dict(L_pn_um=L_PN, width=WIDTH)
    lines = [
        f"PN section rib_1550nm_TE_pn, W = {WIDTH} um, slab {SLAB_WIDTH} um; doping from cornerstone_process.lbr",
        f"2D cross-section normalised to the doped arc, {L_PN:.2f} um.  anode = Via_P, cathode = Via_N.",
    ]
    with lumapi.DEVICE(hide=True) as d:
        setup(d, gds)

        # ---- 1. steady-state bias sweep, carriers exported for step 5 ----
        d.select("CHARGE")
        d.set("solver mode", "steady state")
        d.set("solver type", "gummel")
        d.select("CHARGE::boundary conditions::anode")
        d.set("sweep type", "range")
        d.set("range start", 0.0)
        d.set("range stop", a.vmin)
        d.set("range num points", a.points)
        d.select("CHARGE::charge")
        d.set("save data", 1)
        d.set("filename", str(mat))
        d.save(str(ldev))
        d.run()
        anode = d.getresult("CHARGE", "anode")
        V, current = np.real(np.ravel(anode["V_anode"])), np.real(np.ravel(anode["I"]))
        ch = d.getresult("CHARGE::charge", "charge")
        res.update(
            V=V,
            I=current,
            y=np.squeeze(ch["y"]) / um,
            z=np.squeeze(ch["z"]) / um,
            n=np.real(np.squeeze(ch["n"])).astype(np.float32),
            p=np.real(np.squeeze(ch["p"])).astype(np.float32),
            elements=np.asarray(ch["connectivity"]),
        )
        dop = d.getresult("CHARGE", "doping")
        acceptors, donors = np.real(np.squeeze(dop["NA"])), np.real(np.squeeze(dop["ND"]))
        acceptors = acceptors[:, 0] if acceptors.ndim > 1 else acceptors
        donors = donors[:, 0] if donors.ndim > 1 else donors
        dy, dz = np.squeeze(dop["y"]) / um, np.squeeze(dop["z"]) / um
        res.update(
            NA=acceptors.astype(np.float32),
            ND=donors.astype(np.float32),
            doping_y=dy,
            doping_z=dz,
            doping_elements=np.asarray(dop["connectivity"]),
        )
        net = donors - acceptors  # cm^-3
        junction = junction_position(dy, dz, net)
        res["junction_y_um"] = junction
        half = WIDTH / 2

        def mean(y0: float, y1: float, z0: float, z1: float) -> float:
            inside = lambda y, z: (y > y0) & (y < y1) & (z > z0) & (z < z1)  # noqa: E731
            return region_mean(dy, dz, dop["connectivity"], net, inside)

        lines += [
            f"steady state: {len(V)} points, V = {V.max():.2f} ... {V.min():.2f} V; leakage at {V.min():.1f} V: {current[np.argmin(V)]:.3g} A",
            "doping check: net doping (donors - acceptors, cm^-3) averaged over each region of the solver mesh",
            f"  p slab, lower 100 nm   {mean(-0.78, -half - 0.03, 0.0, T_SLAB):+.3g}   (published: -5.7e17)",
            f"  p rib, upper 120 nm    {mean(-half, 0.0, T_SLAB, T_SI):+.3g}   (published: -2.25e17)",
            f"  n slab, lower 100 nm   {mean(half + 0.03, 0.73, 0.0, T_SLAB):+.3g}   (published: +1.1e18)",
            f"  p contact              {mean(-4.0, -2.0, 0.0, T_SLAB):+.3g}   (published: -1e20)",
            f"  junction at y = {junction * 1000:+.0f} nm from the core centre "
            f"(expected {1000 * (half - t.N_SIDEWALL_DEPTH):+.0f} nm: 110 nm inside the n-side sidewall)",
        ]
        print("\n".join(lines[-7:]), f"({time.time() - t0:.0f} s)", flush=True)

        # ---- 2. small signal: C(V) and Rs ----
        if not a.no_ssac:
            d.switchtolayout()
            d.select("CHARGE::charge")
            d.set("save data", 0)
            d.select("CHARGE")
            d.set("solver mode", "ssac")
            d.set("solver type", "newton")  # ssac needs newton
            d.set("perturbation amplitude", 1e-3)
            d.select("CHARGE::boundary conditions::anode")
            d.set("apply ac small signal", "all")
            C = np.full((len(a.freqs), len(V)), np.nan)
            Rs = np.full_like(C, np.nan)
            for i, freq in enumerate(a.freqs):
                d.switchtolayout()
                d.select("CHARGE")
                d.set("frequency", freq)
                d.run()
                ac = d.getresult("CHARGE", "ac_anode")
                i_ac, v_ac = np.ravel(ac["dI"]), np.ravel(ac["dV_anode"])
                v_ac = v_ac if len(v_ac) == len(i_ac) else np.full(len(i_ac), v_ac[0])
                Y = i_ac / v_ac
                C[i], Rs[i] = np.imag(Y) / (2 * np.pi * freq), np.real(1 / Y)
                print(f"  ssac {freq:.0e} Hz done ({time.time() - t0:.0f} s)", flush=True)
            c_v, rs_v = C[0], Rs[-1]  # capacitance at the lowest frequency, resistance at the highest
            f_rc = 1 / (2 * np.pi * rs_v * c_v)
            res.update(freqs=np.array(a.freqs), C_f=C, Rs_f=Rs, C_V=c_v, Rs_V=rs_v, f_RC=f_rc)
            lines.append(f"\nsmall signal, whole PN section ({L_PN:.1f} um):")
            lines.append(f"{'V':>6} {'C (fF)':>8} {'C (fF/um)':>10} {'Rs (ohm)':>9} {'Rs (ohm cm)':>12} {'f_RC (GHz)':>11}")
            lines += [
                f"{V[k]:6.2f} {c_v[k] * 1e15:8.2f} {c_v[k] * 1e15 / L_PN:10.3f} {rs_v[k]:9.2f} {rs_v[k] * L_PN * 1e-4:12.3f} {f_rc[k] / 1e9:11.1f}"
                for k in range(len(V))
            ]
            lines.append(
                f"C from Im(Y)/omega at {a.freqs[0]:.0e} Hz, Rs from Re(1/Y) at {a.freqs[-1]:.0e} Hz. "
                "f_RC is the intrinsic junction limit, without pads, traces or the driver impedance."
            )
            print("\n".join(lines[-len(V) - 3 :]), flush=True)
        d.switchtolayout()
        d.save(str(ldev))
    np.savez(OUT / f"{NAME}_charge.npz", **res)
    (OUT / f"{NAME}_charge.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
