"""photonics-layout-cookbook: silicon-photonics layout recipes with gdsfactory.

Sub-packages (none of them imports gdsfactory at import time):

* :mod:`photonics_cookbook.process`   -- foundry process files (roles, PDK names, stack, doping)
* :mod:`photonics_cookbook.devices`   -- device recipes as tool-independent geometry
* :mod:`photonics_cookbook.lumerical` -- GDS -> Ansys Lumerical bridge (FDTD / MODE / CHARGE)

These import gdsfactory: :mod:`photonics_cookbook.pdk` (gdsfactory PDKs generated
from the process files) and :mod:`photonics_cookbook.cells` (the cookbook cells).
"""

__version__ = "0.1.0"
