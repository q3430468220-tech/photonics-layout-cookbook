"""photonics-layout-cookbook: silicon-photonics layout recipes with gdsfactory.

Sub-packages (none of them imports gdsfactory at import time):

* :mod:`photonics_cookbook.process`   -- foundry process adapters (roles, stack, doping)
* :mod:`photonics_cookbook.devices`   -- device recipes as tool-independent geometry
* :mod:`photonics_cookbook.lumerical` -- GDS -> Ansys Lumerical bridge (FDTD / MODE / CHARGE)

gdsfactory cells live in :mod:`photonics_cookbook.cells` (imports gdsfactory).
"""

__version__ = "0.1.0"
