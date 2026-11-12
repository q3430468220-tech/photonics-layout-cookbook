"""Design-rule check for CORNERSTONE SOI220A, in pure Python (klayout.db, no GUI).

It applies the published rules collected in cornerstone_technology.py:

    * minimum feature and minimum gap of every mask layer             [DG Table 3][YAML]
    * a via must lie inside P++ or N++ with a 500 nm margin            [DG 5.3]
    * a via must lie inside the electrode with a 500 nm margin         [DG 5.3]
    * high-dose implants must not overlap the waveguide core           [DG 5.3]
    * the low-dose n implant must lie inside the low-dose p implant    [DG Table 2]
    * gratings must not overlap vias or electrodes                     [DG 5.3]
    * the detector window keeps 5 um to electrodes and avoids vias     [DG 5.3]

One deliberate difference from the foundry's own pre-DRC script: electrode features between 2 um
and 6 um wide are reported as a *warning*, not an error.  The official heater building block draws
its filament 2 um wide in the electrode layer, so that width is legal for heater filaments only.

This is a pre-check.  CORNERSTONE runs the binding DRC on every submission.

    python cornerstone_drc.py chip.gds          # writes chip_drc.lyrdb for KLayout's marker browser
    python cornerstone_drc.py --demo            # self-test on a layout with planted violations

    from cornerstone_drc import run_drc
    assert run_drc(component).passed
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import klayout.db as kdb
import klayout.rdb as rdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cornerstone_technology as t

HEATER_WIDTH = t.DESIGN_RULES["heater_filament_width"]
# Width and gap are measured between edges that are closer to parallel than this angle, so that
# 90 deg corners and wide wedges are not reported.  The foundry's pre-DRC script uses 1 deg; a
# layout that passes here with 45 deg also passes there.
ANGLE_LIMIT = 45.0
# A curved shape is a polygon whose chords fall a fraction of a nanometre inside the true curve.
# Only the heater filament is drawn exactly at its limit, so only that check gets a tolerance.
CURVE_TOLERANCE = 0.002


@dataclass
class DrcResult:
    errors: dict[str, int] = field(default_factory=dict)
    warnings: dict[str, int] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        lines = [
            f"DRC {'passed' if self.passed else 'FAILED'}: {sum(self.errors.values())} errors, "
            f"{sum(self.warnings.values())} warnings"
        ]
        lines += [f"  error    {n:4d}  {rule}" for rule, n in self.errors.items()]
        lines += [f"  warning  {n:4d}  {rule}" for rule, n in self.warnings.items()]
        return "\n".join(lines)


def _load(source) -> tuple[kdb.Layout, kdb.Cell]:
    """Accept a gdsfactory component or a GDS path."""
    if isinstance(source, (str, Path)):
        layout = kdb.Layout()
        layout.read(str(source))
        tops = [c for c in layout.top_cells() if not c.name.startswith("$$$")]
        return layout, max(tops, key=lambda c: c.bbox().area())
    return source.kcl.layout, source.kcl.layout.cell(source.cell_index())


def run_drc(source, rdb_path: str | Path | None = None) -> DrcResult:
    """Check a component or GDS file.  ``rdb_path`` writes a KLayout marker database."""
    layout, cell = _load(source)
    dbu = layout.dbu

    def region(key: str) -> kdb.Region:
        layer, datatype = tuple(getattr(t.LAYER, key))
        index = layout.find_layer(layer, datatype)
        return kdb.Region() if index is None else kdb.Region(cell.begin_shapes_rec(index)).merged()

    def um(value: float) -> int:
        return round(value / dbu)

    result = DrcResult()
    report = rdb.ReportDatabase("cornerstone_soi220a_drc")
    report_cell = report.create_cell(cell.name)

    def record(rule: str, markers, severity: str = "error") -> None:
        """Store the markers; the count is the number of distinct places, not of edge pairs."""
        if markers.is_empty():
            return
        if isinstance(markers, kdb.EdgePairs):
            sites = kdb.Region()
            for pair in markers.each():
                sites.insert(pair.bbox().enlarged(1, 1))
            sites = sites.merged()
        else:
            sites = markers.merged()
        (result.errors if severity == "error" else result.warnings)[rule] = sites.count()
        category = report.create_category(f"{severity}: {rule}")
        report.create_items(report_cell.rdb_id(), category.rdb_id(), kdb.CplxTrans(dbu), sites)

    def width(r: kdb.Region, d: float) -> kdb.EdgePairs:
        return r.width_check(um(d), False, kdb.Metrics.Euclidian, ANGLE_LIMIT)

    def space(r: kdb.Region, d: float) -> kdb.EdgePairs:
        return r.space_check(um(d), False, kdb.Metrics.Euclidian, ANGLE_LIMIT)

    # ---- minimum feature and gap of each layer ----
    regions = {key: region(key) for key in t.MIN_WIDTH_SPACE}
    for key, (min_width, min_space) in t.MIN_WIDTH_SPACE.items():
        name = t.OFFICIAL_LAYER_NAMES[key]
        r = regions[key]
        if r.is_empty():
            continue
        if key == "ELECTRODE_LF":
            too_narrow = width(r, HEATER_WIDTH - CURVE_TOLERANCE)
            record(f"{name}: feature narrower than {HEATER_WIDTH} um (heater filament width)", too_narrow)
            narrow = width(r, min_width)
            if narrow.count() > too_narrow.count():
                record(f"{name}: feature narrower than {min_width} um -- allowed for heater filaments only", narrow, "warning")
        else:
            record(f"{name}: feature narrower than {min_width} um", width(r, min_width))
        record(f"{name}: gap smaller than {min_space} um", space(r, min_space))

    core = regions["SI_ETCH2_LF_120NM"]
    p_low, n_low = regions["P_IMPLANT_LOW_DF"], regions["N_IMPLANT_LOW_DF"]
    high = (regions["P_IMPLANT_HI_DF"] + regions["N_IMPLANT_HI_DF"]).merged()
    via, metal = regions["VIA_DF"], regions["ELECTRODE_LF"]
    grating, detector = regions["SI_ETCH1_DUV_DF_70NM"], regions["DETECTOR_IMPLANT_DF"]

    # ---- rules between layers ----
    margin = t.DESIGN_RULES["via_enclosure_by_high_dose"]
    record(f"Via_DF: not enclosed by P++ / N++ with {margin} um margin", via - high.sized(-um(margin)))
    margin = t.DESIGN_RULES["via_enclosure_by_electrode"]
    record(f"Via_DF: not enclosed by Electrode_LF with {margin} um margin", via - metal.sized(-um(margin)))
    record("P++ / N++ overlaps the waveguide core (Si_Etch2_LF_120nm)", high & core)
    record("N_Implant_Low_DF outside P_Implant_Low_DF (n concentration will be higher than specified)", n_low - p_low)
    record("Si_Etch1 grating overlaps Via_DF or Electrode_LF", grating & (via + metal))
    record("Detector_Implant_DF overlaps Via_DF or Electrode_LF", detector & (via + metal))
    gap = t.DESIGN_RULES["detector_to_electrode"]
    record(f"Detector_Implant_DF closer than {gap} um to Electrode_LF", detector.separation_check(metal, um(gap)))

    if rdb_path is not None:
        report.save(str(rdb_path))
    return result


def demo_component():
    """A small layout with one planted violation per rule family (for the self-test)."""
    import gdsfactory as gf

    c = gf.Component()
    c.add_polygon([(0, 0), (20, 0), (20, 0.30), (0, 0.30)], layer=t.CORE)  # core narrower than 0.35
    c.add_polygon([(0, 0.45), (20, 0.45), (20, 0.90), (0, 0.90)], layer=t.CORE)  # gap 0.15 < 0.20
    c.add_polygon([(0, 5), (10, 5), (10, 15), (0, 15)], layer=t.N_HI)
    c.add_polygon([(1, 6), (9.8, 6), (9.8, 14), (1, 14)], layer=t.VIA)  # only 0.2 um inside N++
    c.add_polygon([(0.5, 5.5), (9.9, 5.5), (9.9, 14.5), (0.5, 14.5)], layer=t.METAL)  # only 0.1 um around the via
    c.add_polygon([(30, 0), (60, 0), (60, 2), (30, 2)], layer=t.METAL)  # 2 um filament -> warning
    c.add_polygon([(30, 4), (60, 4), (60, 12), (30, 12)], layer=t.METAL)  # only 2 um from the filament
    c.add_polygon([(0, 20), (5, 20), (5, 25), (0, 25)], layer=t.N_LOW)  # n without the background p
    return c


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    here = Path(__file__).resolve().parent
    if argv[0] == "--demo":
        component = demo_component()
        result = run_drc(component, rdb_path=here / "cornerstone_drc_demo.lyrdb")
        print(result.summary())
        expected = 6
        print(f"self-test: {len(result.errors)} error rules triggered, expected at least {expected}")
        return 0 if len(result.errors) >= expected and result.warnings else 1
    gds = Path(argv[0])
    result = run_drc(gds, rdb_path=gds.with_name(gds.stem + "_drc.lyrdb"))
    print(result.summary())
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
