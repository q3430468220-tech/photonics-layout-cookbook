"""The multiplier in INTERCONNECT: the circuit of svd_model.Circuit as elements, through the class of the mesh chapter.

interconnect.Mesh (lumerical_simulations/clements_mesh/scripts) builds any circuit of mesh_model.Circuit: a coupler is
joined by the row it calls "upper" and the other, so the couplers of the attenuators, which join a row and its dump,
are built as they are.  The analyser has an input on every row, the dumps too, which ends them.  Only the rows of the
light are fed: measure() runs one input after the other and returns T[lam, out, in] for all outputs.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "clements_mesh" / "scripts"))  # the circuit of the mesh

import interconnect as icx
import numpy as np

write_sparameters = icx.write_sparameters


class Multiplier(icx.Mesh):
    def measure(self, inputs=None) -> tuple[np.ndarray, np.ndarray]:
        """T[lam, out, in] for the given inputs (default: every row) and the wavelengths (um)."""
        ic, n = self.ic, self.c.n
        inputs = list(range(n)) if inputs is None else list(inputs)
        columns, lam = [], None
        for i in inputs:
            ic.switchtodesign()
            if self.fed is not None:
                ic.disconnect("ONA", "output", *self.first[self.fed])
            ic.connect("ONA", "output", *self.first[i])
            self.fed = i
            ic.run()
            names = set(str(ic.getresult("ONA")).split("\n"))
            col = []
            for k in range(n):
                name = f"input {k + 1}/mode 1/transmission"
                if name not in names:  # no light at all reaches this input: read as zero
                    col.append(None)
                    continue
                r = ic.getresult("ONA", name)
                key = next(key for key in r if key.endswith("transmission"))
                w = np.ravel(r["wavelength"]) * 1e6
                order = np.argsort(w)
                lam = w[order]
                col.append(np.ravel(r[key])[order])
            size = next(len(x) for x in col if x is not None)
            columns.append(np.array([np.zeros(size, complex) if x is None else x for x in col]))
        u = np.stack(columns, axis=-1)  # (out, lam, in)
        return np.transpose(u, (1, 0, 2)), lam
