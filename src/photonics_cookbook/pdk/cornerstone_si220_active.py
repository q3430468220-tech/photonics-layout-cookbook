"""CORNERSTONE 220 nm SOI *active* PDK for gdsfactory.

= gdsfactory's open ``cspdk.si220`` (passive layers, cells, models)
+ the active layers of the cookbook process file (P, N, PPP, NPP, VIA, METAL)
+ the ``rib_pn`` cross-section and the cookbook cells (``ring_modulator``, ``straight_pn``).

Used exactly like any gdsfactory PDK package::

    import gdsfactory as gf
    from photonics_cookbook.pdk.cornerstone_si220_active import PDK, LAYER

    PDK.activate()
    c = gf.get_component("ring_modulator")
    c.write_gds("ring.gds")
    print(LAYER.NPP)            # -> NPP, i.e. (11, 0)

Layer numbers and doses: see ``process/data/cornerstone_si220_active.yaml``.
"""

from __future__ import annotations

from gdsfactory.config import CONF

from photonics_cookbook.pdk import get_pdk

PROCESS = "cornerstone_si220_active"

PDK = get_pdk(PROCESS)
LAYER = PDK.layers
LAYER_STACK = PDK.layer_stack
LAYER_VIEWS = PDK.get_layer_views()

# Let gdsfactory auto-activate this PDK (gf.get_active_pdk()) when nothing is active,
# just as importing cspdk.si220 does for cspdk.
CONF.pdk = __name__


def activate_pdk() -> None:
    """Activate the CORNERSTONE 220 nm active PDK."""
    PDK.activate()


__all__ = ["LAYER", "LAYER_STACK", "LAYER_VIEWS", "PDK", "PROCESS", "activate_pdk"]
