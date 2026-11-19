"""The drawn mesh in INTERCONNECT: the same pieces as mesh_model.Circuit, as elements, and its measured matrix.

    coupler     an "Optical N Port S-Parameter" element that reads a file with the FDTD S-parameters of the coupler,
                moved to the ends of its cell.  The run excited port 1 only; the coupler is symmetric under both
                mirrors, so S11 = S22 = S33 = S44, S21 = S12 = S34 = S43, S31 = S13 = S24 = S42 and
                S41 = S14 = S23 = S32 give the whole matrix.
    waveguide   a "Straight Waveguide" for every piece: its length, n_eff (plus the change of a warm site), n_g and
                the loss.  Neighbouring pieces without a site are joined into one element.
    analyser    an "Optical Network Analyzer" with one input per output of the mesh.  For each input of the mesh the
                analyser's output is moved to it and the circuit is run: one run gives one column of the matrix.

measure() returns U[lam, out, in], complex, at the wavelengths of the analyser.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from mesh_model import Circuit, Physics

C0 = 299792458.0
PORTS = ("port 1", "port 2", "port 3", "port 4")
# which FDTD result is the entry (out, in) of the coupler: the symmetry of the drawn coupler
SYMMETRY = {(1, 1): 1, (2, 2): 1, (3, 3): 1, (4, 4): 1, (2, 1): 2, (1, 2): 2, (3, 4): 2, (4, 3): 2,
            (3, 1): 3, (1, 3): 3, (2, 4): 3, (4, 2): 3, (4, 1): 4, (1, 4): 4, (2, 3): 4, (3, 2): 4}  # fmt: skip


def write_sparameters(ph: Physics, path: Path, couplers: dict | None = None) -> Path:
    """The file of the coupler, at the wavelengths of the FDTD run, in INTERCONNECT's format.  couplers: an optional
    replacement {"lam": um, 3: S31, 4: S41} (step 4); the reflections are then those of the FDTD coupler."""
    lam = ph._lam
    s = ph.coupler(lam)
    if couplers is not None:
        s = {**s, 3: couplers[3], 4: couplers[4]}
    freq = C0 / (lam * 1e-6)
    order = np.argsort(freq)
    lines = [f'["{p}","{side}"]' for p, side in zip(PORTS, ("LEFT", "LEFT", "RIGHT", "RIGHT"), strict=False)]
    for out in range(1, 5):
        for inp in range(1, 5):
            v = s[SYMMETRY[(out, inp)]][order]
            # the phase is written unwrapped: INTERCONNECT interpolates it linearly between the samples, and a jump of
            # 2 pi between two samples would put a wrong phase at every frequency in between
            angle = np.unwrap(np.angle(v))
            lines.append(f'("port {out}","TE",1,"port {inp}",1,"transmission")')
            lines.append(f"({len(freq)},3)")
            lines += [f"{f:.10e} {abs(x):.10e} {a:.10e}" for f, x, a in zip(freq[order], v, angle, strict=False)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class Mesh:
    """The circuit in an INTERCONNECT session."""

    def __init__(self, ic, c: Circuit, ph: Physics, sparameters: Path | dict, lam_max: float, points: int):
        """sparameters: one file for every coupler, or {coupler id: file}.  The analyser's frequencies are centred on
        lam0, so that lam0 is a sample when the number of points is odd, and reach down to lam_max (um)."""
        self.ic, self.c, self.ph = ic, c, ph
        ic.switchtodesign()
        ic.deleteall()
        f0 = C0 / (ph.lam0 * 1e-6)
        ic.addelement("Optical Network Analyzer")
        ic.set("name", "ONA")
        ic.set("input parameter", "center and range")
        ic.set("center frequency", f0)
        ic.set("frequency range", 2 * (f0 - C0 / (lam_max * 1e-6)))
        ic.set("number of points", points)
        ic.set("number of input ports", c.n)
        for k in range(len(c.couplers)):
            ic.addelement("Optical N Port S-Parameter")
            ic.set("name", f"DC{k}")
            ic.set("load from file", True)
            path = sparameters if isinstance(sparameters, Path) else sparameters[k]
            ic.set("s parameters filename", str(path).replace("\\", "/"))
        self.sites: dict[int, str] = {}  # site -> element name
        self.first, self.last = {}, {}  # row -> (element, port)
        for m in range(c.n):
            prev = None
            pieces = self._join(c.rows[m])
            for i, piece in enumerate(pieces):
                if piece[0] == "dc":
                    k = piece[2]
                    upper = c.couplers[k]["upper"] == m
                    here = (f"DC{k}", "port 2" if upper else "port 1")
                    there = (f"DC{k}", "port 3" if upper else "port 4")
                else:
                    name = f"W{m}_{i}"
                    _, _, length, site = piece
                    ic.addelement("Straight Waveguide")
                    ic.set("name", name)
                    ic.set("length", length * 1e-6)
                    ic.set("frequency", C0 / (ph.lam0 * 1e-6))
                    ic.set("effective index 1", ph.neff)
                    ic.set("group index 1", ph.ng)
                    ic.set("dispersion 1", 0.0)
                    ic.set("loss 1", ph.alpha * 1e6 * 20 / np.log(10))  # dB/m
                    if site >= 0:
                        self.sites[site] = name
                    here, there = (name, "port 1"), (name, "port 2")
                if prev is None:
                    self.first[m] = here
                else:
                    ic.connect(prev[0], prev[1], here[0], here[1])
                prev = there
            self.last[m] = prev
            ic.connect(prev[0], prev[1], "ONA", f"input {m + 1}")
        self.fed = None

    @staticmethod
    def _join(pieces: list) -> list:
        """Join neighbouring waveguide pieces that carry no site into one."""
        out = []
        for p in pieces:
            if p[0] == "wg" and p[3] < 0 and out and out[-1][0] == "wg" and out[-1][3] < 0:
                out[-1] = ("wg", out[-1][1], out[-1][2] + p[2], -1)
            else:
                out.append(p)
        return out

    def set_sites(self, site_dn) -> None:
        ic = self.ic
        ic.switchtodesign()
        for site, name in self.sites.items():
            ic.setnamed(name, "effective index 1", float(self.ph.neff + site_dn[site]))

    def measure(self) -> tuple[np.ndarray, np.ndarray]:
        """U[lam, out, in] and the wavelengths (um), one run per input."""
        ic, n = self.ic, self.c.n
        columns, lam = [], None
        for i in range(n):
            ic.switchtodesign()
            if self.fed is not None:
                ic.disconnect("ONA", "output", *self.first[self.fed])
            ic.connect("ONA", "output", *self.first[i])
            self.fed = i
            ic.run()
            # an analyser input that no light reaches has no result at all (a perfect null, such as the cross port of
            # a block at theta = pi): it is read as zero
            names = set(str(ic.getresult("ONA")).split("\n"))
            col = []
            for k in range(n):
                name = f"input {k + 1}/mode 1/transmission"
                if name not in names:
                    col.append(None)
                    continue
                r = ic.getresult("ONA", name)
                key = next(key for key in r if key.endswith("transmission"))
                w = np.ravel(r["wavelength"]) * 1e6
                order = np.argsort(w)
                lam = w[order]
                col.append(np.ravel(r[key])[order])
            size = next(len(x) for x in col if x is not None)
            columns.append(np.array([np.zeros(size, complex) if x is None else x for x in col]))  # (out, lam)
        u = np.stack(columns, axis=-1)  # (out, lam, in)
        return np.transpose(u, (1, 0, 2)), lam
