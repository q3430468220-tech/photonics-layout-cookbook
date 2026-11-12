# photonics-layout-cookbook

**一门与代工厂工艺兼容的硅光设计课：同一套工艺，版图和仿真各描述一次，并用一个带加热器调谐的微环调制器把两者都走一遍。**

[English](README.md) | [简体中文](README_zh-CN.md)

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)
![gdsfactory](https://img.shields.io/badge/layout-gdsfactory%209-6f42c1)
![lumerical](https://img.shields.io/badge/simulation-Ansys%20Lumerical-orange)
![version](https://img.shields.io/badge/version-0.3-2f8f5b)

## 为什么要有这门课

多数学生学习微环调制器的仿真，是在仿真软件里直接画结构，再手工输入膜层堆叠。代工厂的做法恰好相反：工艺是固定的，交出去的只有版图，因此仿真必须描述这份版图在该工艺下会变成什么样。不遵守这条规则的仿真，可能算对了一个错误的器件。

本仓库完整展示了代工厂的这套思路。它使用一个教学工艺，其中的数值全部来自公开资料，因此每个文件都可以公开、修改，甚至改坏。

<p align="center"><img src="assets/design_flow.png" width="100%" alt="设计流程：用 GDS 文件完成器件版图，用 Layer Builder 进行器件仿真，生成紧凑模型，再做电路仿真，下方是 GSiP 教学 PDK"></p>

**图 1.** 设计流程。排版参照 Ansys 与 Tower Semiconductor 研讨会（2025）的设计流程图。四个阶段的内容均来自本仓库。三个图标取自研讨会幻灯片，见[版权声明](assets/third_party/ansys_workshop/NOTICE.md)。本课程与 Ansys 和 Tower Semiconductor 没有隶属或背书关系。

从左往右读这张图。器件先用 gdsfactory 画出，并写成 GDS 文件。Layer Builder 读入这份文件，同时读入工艺文件（process file）。工艺文件描述同一工艺的膜层堆叠、材料和掺杂。随后，仿真在搭好的结构上运行。任何仿真脚本里都没有厚度、材料或掺杂浓度，这些数值都保存在工艺设计套件（PDK）和工艺文件中。PDK 用 Python 描述工艺，工艺文件则由同一工艺的 CSV 表编译而成。两者取自同一组数字，只要其中一处不一致，测试就会失败。

这门课的思路可以用一句话概括：**同一工艺，描述两次，取自同一组数字。** 第一次描述是 PDK，用于版图。第二次描述是工艺文件，以 CSV 表的形式书写，编译后用于仿真。器件用第一种描述来画，用第二种描述来仿真。改动一个数字时，两处描述都要改；工艺表的测试会指出两处不一致的地方。

## 先看结果

整个流程最终得到一个可以核对数字的器件。环的半径为 10 µm，与总线波导之间的间距为 0.37 µm。通过对结施加反向偏压来调谐，由加热器设定工作点。合并仿真后，主要结果如下：

| 问题 | 答案 | 步骤 |
|---|---|---|
| 这个间距能达到临界耦合（critical coupling）吗？ | 能，间距为 371 nm 时达到临界耦合；版图采用 0.37 µm | 1, 6 |
| 0 V 时每次往返损耗多少光？ | 0.069 dB，其中 0.056 dB 来自自由载流子 | 6 |
| 谐振的质量如何？ | 加载品质因数（Q）= 31 200，370 nm 时消光比高于 40 dB | 6 |
| 调制速度有多快？ | 约 6 GHz，受光子寿命限制；结本身可达 64 GHz | 3, 6 |
| 反向偏压能把谐振移动多少？ | −4 V 时移动 44.9 pm | 5, 6 |
| 加热器能移动多少？ | 124 pm/mW，因此移过一个自由光谱范围需要 79 mW | 4, 6 |

本页其余部分说明仓库的每个部分如何得出这些数字，以及每项结果能说明什么。

## 课程安排

本课程共五章。每章是一份文档，并附有可以动手运行的步骤。

| 章 | 文档 | 学习内容 | 学完后能做什么 | Lumerical |
|---|---|---|---|---|
| 1 | [docs/pdk.md](docs/pdk.md) | 什么是 PDK，以及如何把工艺写成代码：图层、规则、膜层堆叠、截面 | 读懂任何图层表，并说出每一行控制什么 | 否 |
| 2 | [docs/device.md](docs/device.md) | 如何用 PDK 画出器件，以及每个部分为什么放在那里 | 画出微环调制器及一个变体，运行设计规则检查，解释每一条不通过的规则 | 否 |
| 3 | [gsip_process_file_py/README.md](gsip_process_file_py/README.md) | 同一工艺如何变成 Lumerical 工艺文件，以及文件如何与表格核对 | 编译工艺文件，读懂其核对结果，并找到表格中任一数字的来源 | 是 |
| 4 | [lumerical_simulations/ring_modulator/README.md](lumerical_simulations/ring_modulator/README.md) | 七个仿真步骤，从图层检查到电路元件，以及每一步的陷阱 | 运行一个步骤，读懂其结果，并判断结果是否可信 | 是，运行时需要 |
| 5 | [docs/your_foundry.md](docs/your_foundry.md) | 如何把流程移植到真实的代工厂 PDK，同时不把保密数据放进公开仓库 | 为自己的工艺规划移植，并逐步完成 | 工艺文件部分需要 |

没有 Lumerical，仍然可以做很多事。第 1 章和第 2 章可以完整地做下来：画出器件、运行设计规则检查、读懂膜层堆叠，并在 KLayout 中打开 GDS。也可以运行全部 85 个测试。第 4 章的每个结果文件都可以读取，每张图也都可以根据保存的数据重绘，因为绘图脚本只用 NumPy 和 matplotlib 读取这些文件。只有第 3 章的编译器和第 4 章的仿真需要许可证。

## PDK 速览

PDK 是让版图工具能够在某一工艺上绘图的一整套文件。它包括图层、图层编号、设计规则、材料堆叠，以及使用这些图层的单元。本课程使用一个名为 `gsip_teaching` 的教学 PDK。它是 Chrostowski 与 Hochberg 教材中的 Generic Silicon Photonics（GSiP）工艺，图层编号沿用开源 gdsfactory 通用 PDK 的编号。该 PDK 不代表任何代工厂。

<p align="center"><img src="assets/pdk_stack.png" width="100%" alt="GSiP 教学工艺的截面：按比例绘出的完整膜层堆叠（含后段工艺），以及纵向放大五倍的前段工艺"></p>

**图 2.** 整个工艺的一张截面图。（a）按比例画出的完整膜层堆叠，后段工艺由七个构件组成。（b）前段工艺，纵向放大五倍，并用颜色标出第 2 章微环调制器用到的图层。

图 2 说明了对版图最重要的一点。图层是画出的图形，带有一个 GDS 编号。同一图层还有高度、材料，对于注入层还有掺杂浓度。版图里只携带编号，其余信息由仿真器从工艺文件中获取。

下表按用途对图层分组。编号为 GDS 图层/数据类型，浓度单位为 cm⁻³。

| 类别 | 图层（GDS） | 数值 | 来源 |
|---|---|---|---|
| 硅 | WG (1/0) | 波导芯层，220 nm | [B], [BJ], [GF] |
| | SLAB150 (2/0), SLAB90 (3/0) | 平板层，150 nm 和 90 nm | [B], [GF] |
| | DEEPTRENCH (4/0), UNDERCUT (6/0) | 深沟槽，衬底底切 | [B], [GF] |
| 注入 | N (20/0), P (21/0) | 5 × 10¹⁷ 和 7 × 10¹⁷ | [B] 第 6.2 节 |
| | NP (22/0), PP (23/0) | 3 × 10¹⁸ 和 2 × 10¹⁸ | [B] 第 6.2 节 |
| | NPP (24/0), PPP (25/0) | 5 × 10²⁰ 和 1.9 × 10²⁰ | [B] 第 6.2 节，[BJ] |
| 锗与氮化硅 | GE (5/0) | 锗，500 nm | [B], [BJ], [GF] |
| | GEN (26/0), GEP (27/0) | 锗注入，10¹⁹ | [T] |
| | WGN (34/0) | 氮化硅，350 nm | [GF] |
| 后段工艺 | VIAC (40/0) | 接触孔，连接硅与金属 1 | [B], [GF] |
| | M1 (41/0), M2 (45/0) | 铝，0.7 µm | [B], [GF] |
| | HEATER (47/0) | TiN 薄膜，0.15 µm，10 Ω/sq | 图层来自 [GF]，厚度来自 [T] |
| | VIA1 (44/0), VIA2 (43/0) | 金属层之间的通孔 | [B], [GF] |
| | M3 (49/0) | 铝，2 µm，焊盘 | [GF] |
| | PADOPEN (46/0) | 焊盘上的钝化层开口 | [B] |
| 仅供设计 | FLOORPLAN (64/0), TEXT (66/0), DEVREC (68/0) | 外形轮廓、文字、器件识别 | [B], [GF] |

26 个图层中有 23 个需要流片，其余三个只供设计使用。

代码中的每个数字都带有以下四种来源标记之一：

- **[B]** L. Chrostowski 和 M. Hochberg，*Silicon Photonics Design: From Devices to Systems*，剑桥大学出版社，2015。图层映射（表 10.2）、工艺参数（表 10.1）和掺杂浓度（第 6.2 节）取自该书。
- **[BJ]** T. Baehr-Jones 等，"A 25 Gb/s Silicon Photonics Platform"，arXiv:1203.0767（2012）。这是该书表格所引用的已发表工艺，给出的波导损耗为 2.2 ± 0.8 dB/cm。
- **[GF]** gdsfactory 通用 PDK（MIT 许可证）。它的图层映射和膜层堆叠给出了该书未给出的数字和高度。
- **[T]** 为本仓库选取的教学数值。每个数值都与代码写在一起，并注明选取理由，例如 0.15 µm 的加热器薄膜。

**为什么用教学 PDK，而不用真实的 PDK？** 商业代工厂的完整有源工艺（包括硅层级、注入、锗、加热器和多层金属）都在保密协议（NDA）或许可证下发放，没有公开的版本。开源的 CORNERSTONE SOI220A 工艺是真实的，也是公开的，但它只有一层金属，没有加热器层，因此无法展示完整的后段工艺。它是本仓库的第二个例子，见[第二个工艺](#第二个工艺)。由公开资料构建的工艺可以自由发布、修改，甚至改坏，而且流程与真实工艺完全相同。这些数字是教学用数字，不是任何代工厂的数字，不能用于流片。

## 器件

这个器件是带加热器的微环调制器。环是半径为 10 µm 的脊形波导（rib waveguide）。PN 结沿环的 240° 弧段分布，TiN 加热器在芯层上方沿 270° 弧段分布。总线波导通过一个点耦合器与环相接。第 2 章将构建这个器件。

<p align="center"><img src="assets/rm_layout.png" width="100%" alt="微环调制器版图：整体器件与图层表，硅与注入，接触、金属 1 与加热器，通孔 1 与金属 2，以及全部图层叠加"></p>

**图 3.** 器件，由 `rm_builder.py` 绘制。（a）整体器件及图层表。（b）硅与注入：结位于环的上部 240°，n 型在环内，p 型在环外。（c）接触、金属 1 与加热器。（d）通孔 1 与金属 2。（e）全部图层叠加。

默认器件的参数，即 `rm_builder.ring_modulator` 的参数：

| 参数 | 默认值 | 作用 |
|---|---|---|
| `radius` | 10 µm | 环半径；周长为 62.83 µm |
| `width` | 0.5 µm | 环和总线的芯宽，位于 90 nm 厚、6 µm 宽的平板层上 |
| `gap` | 0.37 µm | 环与总线之间的边到边间距；接近第 6 步的临界耦合间距（371 nm） |
| `pn_angle` | 240° | 掺杂弧段，41.89 µm，占环的 67 % |
| `heater_angle` | 270° | 加热器弧段；自由加热丝长 44.72 µm，占环的 71 %，阻值 280 Ω |
| `pad_size`, `pad_pitch` | 80 µm, 100 µm | 金属 3 焊盘：北侧为结的 G S G，南侧为加热器的 H H |

器件共有七个端口：`o1` 和 `o2` 为光端口，`G1`、`S` 和 `G2` 为结的电端口，`H1` 和 `H2` 为加热器的电端口。其设计规则检查结果为 0 个错误、0 个警告。

### 为什么加热器不画在金属 1 上？

这是大多数读者最先问的问题，答案也是这个器件的第一课。加热器和金属 1 都从埋氧层顶面以上 1.10 µm 处开始，因此二者处于同一平面。一个图层只能对应一种材料，所以工艺为加热器单独设置了 HEATER 47/0 图层，为电极单独设置了 M1 41/0 图层。设计规则要求两者至少相距 0.6 µm。如果把加热器画在金属 1 上，它会短路结的接触，加热器本身的电阻也会被金属掩盖。金属 2 随后把电流从加热器的接点引到焊盘。布线属于版图的内容，不属于仿真器。

### 为什么同一个工艺要描述两遍？

因为两种工具读取的内容不同。版图工具需要图层、设计规则和截面，才能画出器件并检查它。仿真器需要每一层的材料、高度和掺杂，才能求解光、载流子和热。如果两份描述都手工编写，它们会逐渐分叉：改动一层，版图变了，仿真却没变，或者反过来。因此，这里有意把工艺描述两遍：一份在 `gsip_technology.py` 中，另一份是 `gsip_process_file_py/gsip_csv` 中的 CSV 表，两者取自同一组数字。`tests/test_process_tables.py` 中的测试会在两者不一致时失败。仿真的第 3 步则逐区域检查，仿真器看到的掺杂是否与表格一致。

### 画出并检查

下面的代码画出默认器件和一个变体（环更大，间距更宽），用设计规则检查两者，并把变体写成 GDS 文件，供 Layer Builder 使用。请在克隆的仓库根目录下运行，且先执行 `uv sync`。若缺少 `build/` 文件夹，写入函数会自动创建它：

```python
import gsip_technology as t  # importing it activates the gsip_teaching PDK
import rm_builder as rm
from gsip_drc import run_drc

device = rm.ring_modulator()                  # default: R = 10 um, gap 0.37 um
variant = rm.ring_modulator(radius=12, gap=0.40)

for name, component in (("default", device), ("variant", variant)):
    result = run_drc(component)
    print(name, result.summary())
    assert result.passed

t.write_gds_for_lumerical(variant, "build/ring_r12.gds", cellname="ring_r12")
```

`run_drc` 是用纯 Python 写成的设计规则检查，因此不需要 Lumerical。它检查最小线宽表中每个图层的最小线宽和最小间距、通孔与接触的包围量、金属 1 与加热器之间的距离，以及注入区的重叠。只要发现任何错误，其 `passed` 标志就为假。它是一个教学工具，只包含器件设计者最先会碰到的几条规则。它不是代工厂的规则文件，也不能代替你投片的代工厂的规则。间距不得小于波导层的最小间距，即 0.2 µm。

## 结果

第 4 章用七个步骤对器件进行仿真，从图层检查一直到电路元件。每一步只回答一个问题，该步骤的图给出答案，数字则来自步骤文件夹中的结果文件。每张图都可以在没有 Lumerical 的情况下，根据保存的数据重绘。

**这些是教学工艺的仿真结果。本文中的任何结果都没有与实际流片的器件做过对比。** 这些数字不属于任何代工厂。[局限与声明](#局限与声明)列出了其背后的假设。

### 第 0 步：Layer Builder 搭出的结构与版图一致吗？

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig0_layer_builder.png" width="100%" alt="Layer Builder 检查：穿过 PN 结段和耦合区的两个剖面，以及穿过成品结构的四个水平切面，分别位于平板层、芯层、金属 1 与加热器、金属 2 所在的高度"></p>

**图 4.** 求解器所见的结构。（a）穿过 PN 结段的剖面。（b）穿过耦合区的剖面。（c 至 f）位于平板层、芯层、金属 1 与加热器以及金属 2 高度的水平切面。

在进行任何物理计算之前，先把模式求解器（MODE）当作探针，用来检查搭好的结构。在完成的三维模型中取十个点，求解器报告它在每一点看到的折射率。这些点包括芯层下方的衬底和埋氧层、接触孔、加热器薄膜和金属 2 导线。结果为：硅 3.476，氧化物 1.444，铝 1.44 + 16i，TiN 3.54 + 6.52i。若工艺文件中的图层表达式写错，这里就会显示为缺失或位置错误的图形。

### 第 1 步：总线如何把光耦合进环？

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig1_coupling.png" width="100%" alt="总线与环之间的耦合：耦合区的场分布；功率耦合系数随间距变化，附指数拟合和临界耦合点；以及随波长变化"></p>

**图 5.** 耦合器。（a）耦合区的场分布，环的弧臂以 S 形弯曲延伸，使四个端口朝向同一方向。（b）功率耦合系数 κ² 随间距的变化，附拟合曲线和临界耦合点。（c）κ² 随波长的变化。

耦合区用时域有限差分法（FDTD）仿真，FDTD 是一种时域求解器。不含总线的参考计算给出环弧臂的损耗，计算时将其除去。在 200、300、400 和 500 nm 的间距下，κ² 分别为 0.118、0.0369、0.0113 和 0.00344。拟合式 κ² = 1.26 · exp(−gap / 84.8 nm) 能再现这些数据，适用范围为 200 至 500 nm 的间距。它只是一个插值公式，不能外推。拟合式给出临界耦合点：间距 371 nm 时 κ² = 0.0159。κ² + t² 的和为 0.9998 至 1.0000，说明求解器守恒功率。在本机上，每个间距约需 6 分钟。

网格决定了 κ² 的可信程度。对 400 nm 间距用三种方式做了计算。耦合区采用 10 nm 网格时，原始 |S41|² 变化 −2.0 %，耗时 18.6 分钟，而默认 20 nm 网格只需 5.6 分钟。表格中使用的是默认的 20 nm 网格。因此 κ² 的精度约为 2 %，这使临界耦合间距移动约 2 nm。

### 第 2 步：无源波导如何导引模式？

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig2_passive.png" width="100%" alt="无源脊形波导：直波导和弯曲波导的模式分布，有效折射率随波长的变化，弯曲损耗随半径的变化，以及 TE0 和 TE1 随芯宽的变化"></p>

**图 6.** 无源脊形波导。（a）直波导模式。（b）弯到 R = 10 µm 的模式，向外移动 26 nm。（c）有效折射率随波长的变化。（d）弯曲损耗随半径的变化。（e）TE0 和 TE1 随芯宽的变化。

模式求解器用于求出截面的模式。在 1550 nm 处，直脊形波导的有效折射率为 2.5677，群折射率为 3.937，TE 成分为 0.987。弯到 10 µm 时，模式向外移动 26 nm，与直波导模式的重叠为 0.995，辐射损耗低于求解器的下限。弯曲损耗在 R = 5 µm 时为 0.56 dB/cm，在 4 µm 时为 15.2 dB/cm，从 6 µm 起低于下限。环的自由光谱范围（FSR）为 λ² / (n_g L)，即 9.71 nm。

图 6（c）中的群折射率取自 1500 至 1600 nm 范围内 n_eff(λ) 的斜率，得到 3.916，比求解器在 1550 nm 处的值低 0.5 %。原因在于材料。Lumerical 在采样波长之间对表列的硅折射率做线性插值，因此材料色散是分段常数，求解器给出的群折射率在 1530 至 1540 nm 之间出现台阶。自由光谱范围采用求解器在 1550 nm 处的值。

**0.5 µm 的脊形波导并非严格单模。** 其 TE1 模式的有效折射率为 2.115，仅比 90 nm 平板层的基模（2.104）高 0.011，因此接近截止。图 6（e）显示了第二个模式出现的位置：在 0.45 µm 宽度时，求解器仍能给出一个 TE1 模式，但其有效折射率低于平板层模式，因此不被导引。TE1 的弯曲损耗没有仿真，这正适合作为第 4 章的一道练习。

**第 2 步与第 5 步的网格教训。** 均匀的 20 nm 网格在 90 nm 平板层表面和芯层侧壁上都没有网格线，而哪些界面有网格线，取决于计算窗口从哪里开始。同一条无掺杂的脊形波导弯到 R = 10 µm 后，在第 2 步的窗口中得到 n_eff = 2.5765，在第 5 步的窗口中得到 2.5693。两者相差 0.007，超过 10 mW 加热器产生的效果。当每个硅表面都有网格线时，两个窗口的结果一致：表中所用的网格在第 2 步得到 2.5702，在第 5 步得到 2.5701。绝对折射率的精度约为 5 × 10⁻⁴。仿真报告的差值（例如随偏压的折射率变化）几乎不受影响。各步骤通过 `common.add_rib_mesh` 添加网格线。使用时要注意一个陷阱：新建的网格对象会取用 Lumerical 中的当前选择，因此该辅助函数必须在设置完求解器对象的最后一个属性之后运行。若在 `addfde()` 之后立即调用，下一条 `set` 语句会报错：“the requested property 'solver type' was not found”。

### 第 3 步：结承载多少电荷，又能以多快的速度改变它？

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig3_charge.png" width="100%" alt="PN 结：净掺杂，0 V 与 4 V 时的载流子，跨结的载流子密度，电容随偏压的变化，RC 带宽，以及工艺文件与求解器的对比"></p>

**图 7.** PN 结。（a）净掺杂。（b、c）0 V 和反向 4 V 时的净载流子。（d）跨结的载流子密度。（e）电容随偏压的变化，附解析公式。（f）本征 RC 带宽。（g）工艺文件与求解器的掺杂对比。

载流子求解器（CHARGE）在二维截面上求解反向偏置结中的载流子。首先，仿真器检查掺杂：在全部六个区域中，净掺杂与工艺表的偏差都在 0.5 % 以内。检查内容是各区域的浓度和横向位置，而不是深度，因为这是建模时就设定好的：掺杂剖面在深度方向上是均匀的。结的位置与设计位置相差 5 nm。

小信号电容取自串联 RC 模型。将导纳 Y 取倒数得到阻抗 Z = 1/Y，串联电阻为 R_s = Re Z，电容为 C = −1/(ω Im Z)。简化式 C = Im(Y)/ω 只在串联电阻可以忽略时才成立，而这里不能忽略。结电容在 0 V 时为 0.398 fF/µm，在 −4 V 时为 0.208 fF/µm。0 V 时串联电阻为 150 Ω，本征 RC 带宽从 64 GHz 升至 131 GHz。

教材 [B] 中的突变结公式（式 6.14）在 0 V 时给出 0.356 fF/µm。仿真值在 0 V 时是该值的 1.12 倍，在 −4 V 时是 1.35 倍。两者之差近似为恒定的附加电容，约 0.04 至 0.05 fF/µm。一维公式没有考虑高 220 nm 的结周围的电场分布。我们认为这是原因，但这一归因尚未经过检验。反向电流保持在 10⁻¹³ A 以下，该值是求解器的数值下限，并不代表漏电预测。

### 第 4 步：加热器向芯层输入多少热量？

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig4_heat.png" width="100%" alt="加热器：10 mW 时的温度分布，穿过加热器的垂直剖面，温升随功率的变化，以及芯层的瞬态响应"></p>

**图 8.** 加热器。（a）10 mW 时的温度分布。（b）穿过加热器的垂直剖面。（c）温升随功率的变化。（d）芯层的瞬态响应。

热仿真（HEAT）采用二维截面模型，包含金属 1 和通孔，结果按加热丝长度归一化。平均值按网格单元的面积加权。在加热段内，芯层每毫瓦升温 2.35 K/mW；在整个环上取平均，则为 1.67 K/mW。紧邻加热器的金属 1 和通孔使其效率降低了 21 %：去掉它们，芯层的温升将达到 2.98 K/mW。加热器薄膜本身的温升为 5.41 K/mW。自由加热丝的阻值为 280 Ω，因此 10 mW 需要 1.67 V 和 6.0 mA。与接点连接以及电流向接点扩展，会使电阻增加几个百分点，此估算未计入这部分。

瞬态计算取参考功率 10 mW。芯层在 10.3 µs 时达到最终温升的 63 %，从 10 % 升到 90 % 需要 34.3 µs。响应不是单指数的，因为热量在扩散：上升时间与时间常数之比为 3.3，而单指数响应给出 2.2。0.35 / t_rise = 10 kHz 只是估计带宽的经验规则，并非实测的 −3 dB 点。

能量守恒检查是脚本的一部分。穿过埋氧层的热流在热沉上积分，结果为 10.00 mW，与设定功率 10.00 mW 相同。环平均假设电极覆盖整段加热丝，但有 6 % 的加热丝位于电极之外。若内侧金属 1 只画 6 µm 宽，而不是延伸到环心，芯层的加热效率将是 2.50 K/mW，而非 2.35 K/mW。

**本步骤的陷阱。** 焦耳热必须作为均匀热源赋予固体加热器，使其在薄膜体内产生。对同一固体施加热功率边界条件看似等价，实则把薄膜从热计算域中切除：芯层温度只相差 0.4 %，但薄膜中央比边缘高出 23 K。把热源画成覆盖薄膜的方盒，问题更严重：它还会加热与之接触的网格单元，到达热沉的功率比设定值多 12 %。发现此类错误的检查很简单：把流入衬底的热流积分起来，与设定功率比较。

### 第 5 步：有源波导如何随偏压和热量变化？

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig5_active.png" width="100%" alt="有源波导随反向偏压的变化：有效折射率变化、损耗、VπL 以及环的谐振漂移"></p>

**图 9.** 有源波导随反向偏压的变化。（a）有效折射率的变化。（b）损耗。（c）VπL。（d）环的谐振漂移。

对弯曲的掺杂脊形波导再次求解模式，并把第 3 步的载流子和第 4 步的温度作为网格属性载入。在 −4 V 时，有效折射率变化 1.71 × 10⁻⁴，VπL 为 1.82 V·cm。损耗从 0 V 时的 13.3 dB/cm 降至 −4 V 时的 9.9 dB/cm，而无掺杂波导的损耗为 0.026 dB/cm。PN 段的自由载流子在 0 V 时每次往返损耗 0.056 dB，在 −4 V 时为 0.042 dB。加热器在加热段内使有效折射率每毫瓦变化 4.41 × 10⁻⁴，折合到环上为每毫瓦 124 pm。因此，4 V 的反向偏压使谐振移动的量，相当于 0.36 mW 的加热功率。加热器设定工作点，结则在工作点附近进行调制。

### 第 6 步：环作为电路元件时表现如何？

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig6_circuit.png" width="100%" alt="环作为电路元件：带自由光谱范围的谱，四种偏压下的谐振与解析环的对比，透射随偏压的变化，消光比和 Q 随间距的变化，以及四种加热功率下的谐振"></p>

**图 10.** 作为 INTERCONNECT 元件的环。（a）0 V 时的谱，并标出自由光谱范围。（b）四种偏压下的谐振，附解析全通环。（c）谐振处及其上方半个线宽处的透射，随偏压的变化。（d）消光比随间距的变化。（e）加载 Q 随间距的变化。（f）四种加热功率下的谐振。

环以一个元件的形式放入 INTERCONNECT 电路仿真器，其参数来自第 1 步至第 5 步的结果。每次往返，0 V 时的损耗为 0.069 dB：其中散射损耗为 0.014 dB（取 2.2 dB/cm [BJ]），自由载流子损耗为 0.056 dB。间距为 371 nm 时，环处于临界耦合。设计间距 370 nm 下，加载 Q 为 31 200，线宽为 49.8 pm，消光比高于 40 dB；按这些输入，仿真给出 46 dB。临界耦合附近，消光深度对参数非常敏感：κ² 分别改变 −1 %、0 和 +1 % 时，解析环给出的消光比为 77、46 和 40 dB，而 κ² 本身的精度约为 2 %。在 1547 nm 附近测得的两个谐振间距为 9.67 nm，即自由光谱范围。公式 λ² / (n_g L) 在设计谐振 1551.6 nm 处给出 9.73 nm。绝对波长的精度只取决于绝对折射率的精度。

光子寿命决定光学带宽。以频率计的线宽 c / (λQ) 为 6.2 GHz，这是常用的光子寿命估计。精确的小信号响应还取决于激光失谐量；谐振时，其极点位于该值的一半处。与 64 GHz 的 RC 带宽合在一起，两个级联一阶响应的 −3 dB 点为 6.1 GHz。

−1、−2 和 −4 V 时，谐振漂移分别为 14.9、26.4 和 44.9 pm（第 5 步的结果为 14.8、26.3 和 44.8 pm）。在 0 至 4 V 范围内的平均值为 11.2 pm/V。在 0 V 谐振波长处，0、−1、−2 和 −4 V 时的透射分别为 −46.0、−5.6、−2.5 和 −0.95 dB。加热器使谐振每毫瓦移动 124.0 pm，因此在设计谐振处移过一个自由光谱范围需要 79 mW。

消光比对间距十分敏感：间距为 370 nm 时高于 40 dB，340 nm 和 400 nm 时约为 15 dB。实际设计中应在掩膜上扫描间距。版图的默认值 0.37 µm 即为本例所取的间距。

### 器件数字一览

| 量 | 数值 | 步骤 |
|---|---|---|
| 环半径，周长 | 10 µm，62.83 µm | 版图 |
| PN 段（结的弧段） | 41.89 µm，240°，占环的 67 % | 版图 |
| 加热丝 | 44.72 µm，280 Ω，占环的 71 % | 版图，第 4 步 |
| 临界耦合 | 间距 371 nm 时 κ² = 0.0159 | 1, 6 |
| 直波导在 1550 nm 处的有效折射率与群折射率 | 2.5677 和 3.937 | 2 |
| 0 V 和 −4 V 时的结电容 | 0.398 和 0.208 fF/µm | 3 |
| 0 V 和 −4 V 时的本征 RC 带宽 | 64 和 131 GHz | 3 |
| 加热器效率（加热段内的芯层） | 2.35 K/mW | 4 |
| 热时间常数（63 %）与 10 至 90 % 上升时间 | 10.3 µs 和 34.3 µs；带宽约 10 kHz | 4 |
| −4 V 时的折射率变化与 VπL | 1.71 × 10⁻⁴ 和 1.82 V·cm | 5 |
| 0 V 时每次往返的损耗 | 0.069 dB，其中 0.056 dB 来自自由载流子 | 6 |
| 370 nm 时的加载 Q、线宽与自由光谱范围 | 31 200，49.8 pm，9.67 nm | 6 |
| 0 V 时的消光比 | 高于 40 dB（按这些输入为 46 dB） | 6 |
| 光学带宽 | 6.2 GHz | 6 |
| −4 V 时的谐振漂移 | 44.9 pm | 6 |
| 热调谐 | 124 pm/mW；移过一个自由光谱范围需要 79 mW | 6 |

### 数字说明了什么

- 限制速度的是光子寿命，约 6 GHz，而不是结；结本身允许 64 GHz。要想更快，需要更低的 Q，也就是更小的间距，代价是消光比下降。
- 自由载流子决定了损耗：每次往返的 0.069 dB 中，有 0.056 dB 来自它们。
- 加热器设定工作点，结在工作点附近调制。4 V 的反向偏压相当于 0.36 mW 的加热功率。
- 消光比对间距非常敏感：370 nm 时高于 40 dB，340 nm 和 400 nm 时约为 15 dB。实际设计应在掩膜上扫描间距。
- 紧邻加热器的金属 1 和通孔使其效率损失 21 %。
- 网格比计算窗口更重要。若网格线没有落在 90 nm 平板层表面上，有效折射率会偏移 0.007，这一偏移量超过 10 mW 加热器产生的效果。

这些数字还可以与教材 [B] 对照，共有三处。在 −1 至 −4 V 之间，调制效率为 1.4 至 1.8 V·cm，接近 [B] 图 6.6 中的 1.6 V·cm。[B] 第 6.5.2 节指出，金属加热器置于条形波导上方时，每个自由光谱范围需要 36 mW。这里则需要 79 mW，因为只有 71 % 的环被加热，而且电极吸走了 21 % 的热量。两项修正之后，该值应为 44 mW。[B] 第 13.1.2 节描述了一个脊形波导尺寸相近、掺杂约 75 % 的微环，其电容约 25 fF，0 V 附近的谐振漂移为 28 pm/V，并将 Q 降至 5000，以得到 35 GHz 的带宽。本例中的环掺杂比例为 67 %，电容为 16.7 fF，在 0 至 0.5 V 范围内的漂移为 16.1 pm/V。它处于临界耦合，Q 为 31 200，其光子寿命给出约 6 GHz 的带宽。两个环的半径和间距不同，因此这一比较说明的是取舍关系，而不是数值上的对应。

## 快速开始

版图、设计规则检查和测试只需要 Python。工艺文件和仿真需要带 FDTD 与 CHARGE 许可证的 Ansys Lumerical。本项目使用 [uv](https://docs.astral.sh/uv/) 管理可复现的 Python 环境，支持 Python 3.12 或 3.13。

**请把克隆的仓库放在不含非 ASCII 字符的路径下**，例如直接位于一个简短的纯 ASCII 路径之下的 `photonics-layout-cookbook` 文件夹。否则 Lumerical 求解器可能失败。

```bash
# 1. environment (uv: https://docs.astral.sh/uv/), then the code and the packages
git clone https://github.com/q3430468220-tech/photonics-layout-cookbook.git
cd photonics-layout-cookbook
uv sync

# 2. the PDK: list the layers, the stack and the cross-sections; write the KLayout technology
uv run python gsip_technology.py

# 3. the design-rule check on its own, with planted violations that must be found
uv run python gsip_drc.py --demo

# 4. the device: rm_ring.gds, the DRC report and preview images in build/
uv run python rm_builder.py

# 5. the tests (85, no Lumerical needed)
uv run pytest
```

根据保存的结果文件重绘某一张图，例如第 2 步的无源波导。此操作不需要 Lumerical：

```bash
uv run python lumerical_simulations/ring_modulator/figures/fig2_passive.py
```

### Lumerical 部分

程序通过环境变量 `LUMERICAL_ROOT` 找到 Lumerical，该变量指向包含 `api/python/lumapi.py` 的文件夹。若未设置，则搜索常见的安装位置。

```powershell
# PowerShell
$env:LUMERICAL_ROOT = "C:\Program Files\ANSYS Inc\v251\Lumerical"
```

```bash
# bash
export LUMERICAL_ROOT=/opt/lumerical/v251
```

先编译工艺文件。这需要 FDTD 和 CHARGE 许可证，且不会弹出窗口。编译器会写出 `gsip_process_file_py/gsip_process.lbr`，并重新加载该文件，将其中的每个属性与表格逐项比较，以完成检查。[第 3 章](gsip_process_file_py/README.md)解释了每一张表。

```bash
uv run python gsip_process_file_py/gsip_process_file_compiler.py
```

然后按顺序运行七个步骤，每一步都从 `lumerical_simulations/ring_modulator/scripts/` 中对应的脚本启动。第 1 步提供 `--dry` 选项：它在粗网格上计算一个间距，且不做参考计算，这是确认环境配置是否正确的最省时的办法。第 1 步完整运行时，每个间距约需 6 分钟。带选项的脚本可以用 `--help` 列出全部选项。

```bash
uv run python lumerical_simulations/ring_modulator/scripts/layer_builder_check.py
uv run python lumerical_simulations/ring_modulator/scripts/coupling_coefficient_fdtd.py --dry
uv run python lumerical_simulations/ring_modulator/scripts/passive_mode_fde.py
uv run python lumerical_simulations/ring_modulator/scripts/charge_profile.py
uv run python lumerical_simulations/ring_modulator/scripts/heat_profile.py
uv run python lumerical_simulations/ring_modulator/scripts/active_mode_fde.py
uv run python lumerical_simulations/ring_modulator/scripts/ring_modulator_interconnect.py
```

[第 4 章](lumerical_simulations/ring_modulator/README.md)说明每一步做什么、哪些设置重要，以及每一步返回什么结果。

## 在自己的脚本里使用

版图部分是普通的 Python 包。导入 `gsip_technology` 即激活 PDK，因此画图前要先导入它。[“画出并检查”一节](#画出并检查)中的代码片段展示了这种写法，任何在仓库根目录下运行的脚本都可以使用同样的构建函数。

在 Lumerical 中，Layer Builder 需要一个 GDS 文件和一个工艺文件。可以在脚本或 Layer Builder 对话框中按以下顺序运行这三条命令：

```text
addlayerbuilder;
loadgdsfile("/full/path/to/rm_ring.gds");
loadprocessfile("/full/path/to/gsip_process_file_py/gsip_process.lbr");
```

`addlayerbuilder` 创建对象；`loadgdsfile` 载入 `rm_builder.py` 写出的展平版图；`loadprocessfile` 载入编译好的工艺。三者合在一起，就得到仿真脚本所搭建的结构，因此可以在运行求解器之前，先在 Layer Builder 中检查这一结构。与各步骤脚本一样，两个文件都应给出完整路径（见 `scripts/common.py`）。

## 仓库结构

```text
photonics-layout-cookbook/
├── gsip_technology.py          教学 PDK：图层、规则、膜层堆叠、截面、单元（第 1 章）
├── gsip_drc.py                 纯 Python 设计规则检查，基于 klayout.db；--demo 自检
├── rm_builder.py               微环调制器版图（第 2 章）
├── rm_ring.gds                 它的输出，展平，可直接用于 Layer Builder
├── lumerical_env.py            定位 Lumerical（LUMERICAL_ROOT）并导入 lumapi
├── figstyle.py                 共用的图形样式
├── docs/                       第 1、2、5 章：pdk.md、device.md、your_foundry.md
├── gsip_process_file_py/       第 3 章：以 CSV 表描述的工艺，以及编译器
│   ├── gsip_csv/               工艺表；文件夹中的 README 给出每个数值的来源
│   ├── gsip_process_file_compiler.py   通过 lumapi 把表编译成 gsip_process.lbr
│   └── gsip_process.lbr        编译好的工艺文件，保存在仓库中
├── lumerical_simulations/ring_modulator/   第 4 章
│   ├── scripts/                common.py 及 0 至 6 号步骤各一个脚本
│   ├── 0_layer_builder_check/ … 6_interconnect_ring_modulator/
│   │                           每步：小型 GDS、.txt 摘要、.npz 结果数组（保留）
│   └── figures/                fig0 … fig6 的脚本和 PNG 文件；无需 Lumerical 即可重绘
├── assets/                     本页的图、绘图脚本，third_party/ 中为声明
├── klayout_tech/               layers.lyp 和 tech.lyt，用于在 KLayout 中查看版图
├── tests/                      85 个 pytest 测试：PDK、版图、DRC、工艺表、图
├── more_processes/cornerstone_soi220a/   第二个工艺，自包含，附带自己的测试
├── legacy/                     v0.1 版本，仅供参考，不再维护
├── ROADMAP.md  CONTRIBUTING.md  CITATION.cff  LICENSE
└── pyproject.toml  uv.lock     uv 项目及其锁定的版本
```

## 你自己的代工厂

当数字来自真实的代工厂时，流程并不会改变。[第 5 章](docs/your_foundry.md)给出完整步骤，概括如下：

1. 把 `gsip_technology.py` 中的图层映射、常数、规则和截面，替换为你自己 PDK 的内容。图层名保留代工厂原有的名称。
2. 把 `gsip_process_file_py/gsip_csv/` 中表格的数据行替换为代工厂的数字，并在每个数字旁边记录其来源。所有假设都要标注出来。
3. 把器件生成器移植到代工厂的截面上，并用读取代工厂规则的设计规则检查来验证。
4. 编译工艺文件，并先运行仿真的第 0 步检查。图层表达式写错时，会表现为错误的折射率。
5. 不要把代工厂的数据放进本仓库。保密协议（NDA）下的数据绝对不能进入公开仓库。

## 第二个工艺

[more_processes/cornerstone_soi220a/](more_processes/cornerstone_soi220a/README.md) 在 CORNERSTONE SOI220A 上运行同样的流程。这是南安普顿大学的一个真实且开放的代工厂工艺。该目录自带工艺定义文件、设计规则检查、器件、工艺文件、仿真和测试。在该目录中运行 `uv run pytest`，结果为 24 项通过、1 项跳过。

它能教给读者通用工艺教不了的东西。CORNERSTONE SOI220A 只有一层金属、没有加热器层，因此加热器画在电极层上，与结的电极共享环的周长：结占上部 240°，加热器占下部 76°。它的 n 型注入从侧壁进入脊形波导，所以结的位置并不在掩膜边缘上。代工厂会自动生成每根波导周围的沟槽，工艺文件也对此做了复现。把两个文件夹并排阅读，就能看出工艺改变时哪些内容随之改变，哪些保持不变。通用工艺能说明方法，只有真实工艺才能展示其中的取舍。

这第二个例子保持 v0.2 发布时的样子。本版的修正都没有移植到其中，包括硅界面上的网格线、体积热源、串联 RC 提取和精细化的谐振分析。因此，由于第 2 步所述的网格原因，它的绝对有效折射率可能偏差达几个 10⁻³；其加热器仍使用第 4 步已指出有误的热功率边界条件。阅读其中的数字时请注意这一点。

## 设计原则

每条原则之所以列在这里，是因为本课程依赖于它。

- **同一个工艺，取自同一组数字。** 每个数字在 Python PDK 中写一次，在工艺文件的 CSV 表中再写一次。测试保证两份描述相等，因此它们不会悄悄地不一致。同一个数字的两份副本会逐渐分离，错误随后只会在掩膜或仿真中显现。测试会在仿真运行之前发现这类偏差。
- **GDS 即契约。** Layer Builder 根据 GDS 和工艺文件搭建每一个结构，因此求解器看到的是版图所描述的内容，而不是 Python 代码的本意。仿真脚本中的一些设置读取自 `rm_builder.ring_modulator` 的默认值，这些默认值同样会影响仿真。
- **每个数字都有来源。** 每个数字都标有文献、结果文件或教学选择，每个教学数值还标有 [T] 及其理由。读者可以核对任何数字，课程也可以据此修正。
- **每一层都要用独立的依据核对。** 第 0 步把折射率与预期材料比较；第 3 步把掺杂与表格比较；第 4 步把热流与功率比较。模式求解器的网格也用同样的方法检查：在每个硅表面都有网格线之前，同一条脊形波导得到了两个有效折射率。流程可以前后一致，却仍然是错的，因此每一层都需要各自的检查。
- **只使用公开数据。** 每个数字都来自公开文献，或是有标记的教学数值。公开课程必须能够共享其数据，而代工厂的数据不能共享。
- **仿真保留数据。** 每张图都可以不依赖 Lumerical，根据保存的结果数组重绘。没有许可证的读者仍然可以核对图中的数据。

## 局限与声明

这些局限是结果的一部分。在使用任何数字之前，请先阅读。

- 这些是教学工艺的仿真结果，没有与任何已流片的器件做过对比。流片之前，所有数字都必须以代工厂为准。
- 假设条件包括：侧壁垂直、掺杂剖面均匀（突变结）、上包层平坦、所有通孔和金属均为铝、TiN 数据取自体材料值。CHARGE 和 HEAT 的数据库中没有 TiN，因此薄膜采用铝模型，并覆写了四项属性。在 HEAT 中，顶面为绝缘面，因此没有对流和辐射。
- CHARGE 和 HEAT 使用直的二维截面，只有模式求解器会将波导弯曲。
- 未计入加热器和金属的光吸收。金属 2 位于芯层上方 2.1 µm 处并横跨波导，模式求解器的计算窗口止于加热器下方，芯层与加热器之间有 0.88 µm 的氧化层。
- 网格限制了精度。绝对有效折射率的精度约为 5 × 10⁻⁴，FDTD 步骤中 κ² 的精度约为 2 %。临界耦合附近，消光比的不确定度可达数分贝，临界耦合间距会移动约 2 nm。
- 电路模型不含自热、双光子吸收，也没有焊盘和导线的射频模型。第 3 步的 f_RC 是结的本征极限。
- 2.2 dB/cm 的波导损耗是类似工艺已发表的数值，并非仿真结果。
- 第二个例子 `more_processes/cornerstone_soi220a` 保持 v0.2 发布时的样子，未包含本版的修正。

`assets/third_party/ansys_workshop/` 中的第三方图标取自 Ansys 研讨会幻灯片，并依据[其版权声明](assets/third_party/ansys_workshop/NOTICE.md)使用。本项目与 Ansys、Tower Semiconductor、CORNERSTONE、教材作者以及 gdsfactory 团队均无隶属或背书关系。“Ansys”和“Lumerical”是 ANSYS, Inc. 的商标。

## 路线图

完整计划及每项内容的理由见 [ROADMAP.md](ROADMAP.md)。简要如下：

| 阶段 | 新增内容 | 状态 |
|---|---|---|
| v0.1 | 基于 `cspdk` 生成 PDK 的可安装包 | 已发布，位于 [legacy/](legacy/README.md) |
| v0.2 | CORNERSTONE SOI220A 上的展平流程 | 已发布，位于 [more_processes/cornerstone_soi220a/](more_processes/cornerstone_soi220a/README.md) |
| v0.3 | 本课程：带完整后段工艺的 GSiP 教学 PDK、七个仿真步骤和五章内容 | 本版 |
| 下一步 | 由第 1 至 5 步生成供 INTERCONNECT 使用的微环紧凑模型；工艺角；在掩膜上扫描间距 | 计划中 |
| 以后 | 同一工艺上的更多器件，例如移相器和锗光电探测器 | 计划中 |

## 贡献、引用与许可证

欢迎贡献，尤其是章节、练习、同一工艺上的新器件，以及使用公开数据的新工艺。参见 [CONTRIBUTING.md](CONTRIBUTING.md)。如果本课程对你的研究或教学有所帮助，请按照 [CITATION.cff](CITATION.cff) 中的信息引用。代码以 [MIT 许可证](LICENSE) 发布。

## 参考文献

- L. Chrostowski and M. Hochberg, *Silicon Photonics Design: From Devices to Systems*, Cambridge University Press, 2015, [doi:10.1017/CBO9781316084168](https://doi.org/10.1017/CBO9781316084168)
- T. Baehr-Jones et al., "A 25 Gb/s Silicon Photonics Platform", [arXiv:1203.0767](https://arxiv.org/abs/1203.0767)
- M. Nedeljkovic, R. Soref and G. Z. Mashanovich, "Free-carrier electrorefraction and electroabsorption modulation predictions for silicon over the 1–14 µm infrared wavelength range", IEEE Photonics Journal 3, 1171 (2011), [doi:10.1109/JPHOT.2011.2171930](https://doi.org/10.1109/JPHOT.2011.2171930)
- gdsfactory, [repository](https://github.com/gdsfactory/gdsfactory) and [documentation](https://gdsfactory.github.io/gdsfactory/)
- SiEPIC-Tools with the GSiP library, [repository](https://github.com/SiEPIC/SiEPIC-Tools)
- Ansys Optics, [Layer builder - Simulation object](https://optics.ansys.com/hc/en-us/articles/360034382394-Layer-builder-Simulation-object)
- Ansys Optics, [Ring Modulator](https://optics.ansys.com/hc/en-us/articles/360042322794-Ring-Modulator)
- Ansys Optics, [Workshop: Designing Foundry-Compatible Photonic Components and Circuits](https://optics.ansys.com/hc/en-us/articles/31257798958611-Workshop-Designing-Foundry-Compatible-Photonic-Components-and-Circuits)
- CORNERSTONE, [open PDK repository](https://github.com/cornerstone-uos/cornerstone-pdk)
- [KLayout](https://www.klayout.de/), [uv](https://docs.astral.sh/uv/)
