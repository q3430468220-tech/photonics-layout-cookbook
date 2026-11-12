"""Design-rule check for the GSiP teaching process, in pure Python (klayout.db, no GUI).

It applies the rules collected in gsip_technology.py:

    * minimum width and minimum space of every mask layer
    * enclosures: a contact via inside N++ / P++ and inside metal 1; via 1 inside metal 1 or the
      heater and inside metal 2; via 2 inside metal 2 and metal 3; a pad opening inside metal 3
    * metal 1 and the heater film lie in the same plane and keep a distance
    * N++ and P++ never overlap, N and P never overlap
    * warnings: an implant drawn where there is no silicon; a contact implant close to a waveguide core

A foundry's rule deck has hundreds of rules.  This one has the handful that a device builder trips
over first, so that "the layout passes DRC" means something in the exercises.

    python gsip_drc.py chip.gds          # writes chip_drc.lyrdb for KLayout's marker browser
    python gsip_drc.py --demo            # self-test on a layout with planted violations

    from gsip_drc import run_drc
    assert run_drc(component).passed
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import klayout.db as kdb
import klayout.rdb as rdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gsip_technology as t

# Width and space are checked with KLayout's ignore_angle set to this value.  The limit does not hide corners:
# measured on probes, two squares that touch diagonally, 0.141 um apart corner to corner, give space markers
# against a 0.2 um space, and so does a gap tilted by 10 degrees (0.1 um at one end).
ANGLE_LIMIT = 45.0
RULES = t.DESIGN_RULES

# (inner layer, outer layers, margin, rule text): the inner shape must lie inside the union of the outer
# layers, with the margin on every side.
ENCLOSURES = [
    ("VIAC", ("NPP", "PPP"), RULES["viac_enclosure_by_contact_implant"], "contact via not enclosed by N++ / P++"),
    ("VIAC", ("M1",), RULES["viac_enclosure_by_m1"], "contact via not enclosed by metal 1"),
    ("VIA1", ("M1", "HEATER"), RULES["via1_enclosure_by_lower"], "via 1 not enclosed by metal 1 or the heater"),
    ("VIA1", ("M2",), RULES["via1_enclosure_by_m2"], "via 1 not enclosed by metal 2"),
    ("VIA2", ("M2",), RULES["via2_enclosure_by_m2"], "via 2 not enclosed by metal 2"),
    ("VIA2", ("M3",), RULES["via2_enclosure_by_m3"], "via 2 not enclosed by metal 3"),
    ("PADOPEN", ("M3",), RULES["padopen_enclosure_by_m3"], "pad opening not enclosed by metal 3"),
]
IMPLANTS = ("N", "P", "NP", "PP", "NPP", "PPP")
SILICON = ("WG", "SLAB90", "SLAB150")


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
    cache: dict[str, kdb.Region] = {}

    def region(name: str) -> kdb.Region:
        if name not in cache:
            layer, datatype = tuple(getattr(t.LAYER, name))
            index = layout.find_layer(layer, datatype)
            cache[name] = kdb.Region() if index is None else kdb.Region(cell.begin_shapes_rec(index)).merged()
        return cache[name]

    def union(names) -> kdb.Region:
        total = kdb.Region()
        for name in names:
            total += region(name)
        return total.merged()

    def um(value: float) -> int:
        return round(value / dbu)

    result = DrcResult()
    report = rdb.ReportDatabase("gsip_teaching_drc")
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

    # ---- minimum width and space of each layer ----
    for name, (min_width, min_space) in t.MIN_WIDTH_SPACE.items():
        r = region(name)
        if r.is_empty():
            continue
        record(f"{name}: narrower than {min_width} um", r.width_check(um(min_width), False, kdb.Metrics.Euclidian, ANGLE_LIMIT))
        record(
            f"{name}: space smaller than {min_space} um", r.space_check(um(min_space), False, kdb.Metrics.Euclidian, ANGLE_LIMIT)
        )

    # ---- enclosures ----
    for inner, outers, margin, text in ENCLOSURES:
        record(f"{text} with {margin} um margin", region(inner) - union(outers).sized(-um(margin)))

    # ---- rules between layers ----
    gap = RULES["m1_to_heater"]
    record("metal 1 touches the heater film", region("M1") & region("HEATER"))
    record(f"metal 1 closer than {gap} um to the heater film", region("M1").separation_check(region("HEATER"), um(gap)))
    record("N++ overlaps P++", region("NPP") & region("PPP"))
    # N and P meet along the junction, so their overlap is shrunk by one database unit (1 nm on each side):
    # an overlap of 2 nm or less passes, a wider one is an error
    record("N overlaps P", (region("N") & region("P")).sized(-1))

    # ---- warnings ----
    # 5 nm of tolerance: merged and smoothed slab outlines move by a nanometre or two
    record("implant drawn where there is no silicon", union(IMPLANTS) - union(SILICON).sized(um(0.005)), "warning")
    gap = RULES["contact_implant_to_core"]
    contact = union(("NPP", "PPP"))
    close = contact.separation_check(region("WG"), um(gap)).polygons(1) + (contact & region("WG"))
    record(f"N++ / P++ closer than {gap} um to a waveguide core (optical loss)", close, "warning")

    if rdb_path is not None:
        report.save(str(rdb_path))
    return result


def demo_component():
    """A small layout with one planted violation per rule family (for the self-test)."""
    import gdsfactory as gf

    def rect(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    c = gf.Component()
    c.add_polygon(rect(0, 0, 20, 0.15), layer=t.WG)  # core narrower than 0.2
    c.add_polygon(rect(0, 0.25, 20, 0.75), layer=t.WG)  # gap 0.1 < 0.2
    c.add_polygon(rect(0, 5, 10, 10), layer=t.SLAB90)
    c.add_polygon(rect(0, 5, 6, 10), layer=t.NPP)
    c.add_polygon(rect(4, 5, 10, 10), layer=t.PPP)  # N++ overlaps P++
    c.add_polygon(rect(5.3, 7, 5.9, 7.6), layer=t.VIAC)  # only 0.1 um inside N++
    c.add_polygon(rect(5.25, 6.9, 7.0, 7.7), layer=t.M1)  # only 0.05 um around the via
    c.add_polygon(rect(7.2, 6, 9, 9), layer=t.HEATER)  # 0.2 um from metal 1
    c.add_polygon(rect(8, 7, 9.5, 8.5), layer=t.VIA1)  # sticks out of the heater, no metal 2 above
    c.add_polygon(rect(30, 0, 40, 5), layer=t.N)  # implant with no silicon below
    return c


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    here = Path(__file__).resolve().parent
    if argv[0] == "--demo":
        result = run_drc(demo_component(), rdb_path=here / "gsip_drc_demo.lyrdb")
        print(result.summary())
        expected = 7
        print(f"self-test: {len(result.errors)} error rules triggered, expected at least {expected}")
        return 0 if len(result.errors) >= expected and result.warnings else 1
    gds = Path(argv[0])
    result = run_drc(gds, rdb_path=gds.with_name(gds.stem + "_drc.lyrdb"))
    print(result.summary())
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
