# Third-party icons

The three PNG files in this folder are taken from the slides of the workshop
*Designing Foundry-Compatible Photonic Components and Circuits* by Ansys and Tower Semiconductor
(slides © 2025 ANSYS, Inc.), which Ansys publishes with the article
[Workshop: Designing Foundry-Compatible Photonic Components and Circuits](https://optics.ansys.com/hc/en-us/articles/31257798958611-Workshop-Designing-Foundry-Compatible-Photonic-Components-and-Circuits).

| file | what it shows |
|---|---|
| `layer_builder_icon.png` | the "Build" icon of the Layer Builder |
| `process_file_icon.png` | the process-file pictogram |
| `factory_icon.png` | the factory pictogram of the PDK bar |

They are used in one place: [`assets/design_flow.png`](../../design_flow.png), drawn by
[`assets/scripts/design_flow.py`](../../scripts/design_flow.py). The arrangement of that figure
(four stages in a row, the PDK below them, the colours and the wording of the stage titles) also
follows the design-flow slide of the same workshop. Everything shown inside the stages is drawn
from this repository's own layout and simulation data.

**These files are not covered by the MIT licence of this repository.** All rights stay with their
owners. They are included for illustration and teaching only. "Ansys" and "Lumerical" are
trademarks of ANSYS, Inc.

## A figure without third-party material

The script draws its own icons when this folder is missing, or on request:

```bash
uv run python assets/scripts/design_flow.py --own-icons    # writes build/design_flow_own_icons.png
```

To drop the third-party icons from the repository, delete this folder and run the script again
without the option. It then writes `assets/design_flow.png` with its own icons.
