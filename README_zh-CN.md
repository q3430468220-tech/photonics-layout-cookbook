# photonics-layout-cookbook

用 [gdsfactory](https://github.com/gdsfactory/gdsfactory) 画版图、用 Ansys Lumerical 做仿真的硅光设计教程。从一套 PDK（工艺设计套件）出发，画出一个微环调制器，再对这份版图做仿真：FDTD 算耦合器，MODE 算波导，CHARGE 和 HEAT 算 PN 结和加热器，INTERCONNECT 算电路。

[English](README.md) | [简体中文](README_zh-CN.md) | [网站](https://q3430468220-tech.github.io/photonics-layout-cookbook/)

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)
![gdsfactory](https://img.shields.io/badge/layout-gdsfactory%209-6f42c1)
![lumerical](https://img.shields.io/badge/simulation-Ansys%20Lumerical-orange)
![version](https://img.shields.io/badge/version-0.3-2f8f5b)

做微环调制器仿真，常见的做法是在仿真软件里直接画结构，手工填入膜层厚度和材料。给代工厂做设计时情况不同：工艺是固定的，交付的是版图，仿真要回答的是这份版图按这套工艺做出来是什么样。这个仓库拿一个器件，从版图到电路完整做一遍，代码可以直接运行，也可以随便改。

<p align="center"><img src="assets/design_flow.png" width="100%" alt="设计流程：版图、器件仿真、紧凑模型、电路仿真，下方是 PDK"></p>

*设计流程。这张图参照了 Ansys 与 Tower Semiconductor 研讨会（2025）的一页幻灯片，图中的版图、曲线和数值都来自本仓库。*

这里用的是一套叫 GSiP（generic silicon photonics，通用硅光）的教学工艺。同一套工艺写成了两份：一份是画版图用的 gdsfactory PDK，一份是 Lumerical 的 Layer Builder 用的工艺文件。Layer Builder 是把版图文件（GDS）搭成三维结构的工具。测试会检查两份描述是否一致。画版图用前者，仿真用后者，所以没有哪个仿真脚本需要手工定义结构，厚度、材料和掺杂都来自工艺文件。

## 教程目录

一共五章，建议按顺序读，前两章不需要 Lumerical。各章正文目前是英文，本页是中文概览。

| | 章节 | 内容 |
|---|---|---|
| 1 | [PDK](docs/pdk.md) | 图层、膜层堆叠、截面和设计规则，以及怎样把它们写成代码 |
| 2 | [器件](docs/device.md) | 画微环调制器，再用设计规则检查（DRC）和连通性检查验证版图 |
| 3 | [工艺文件](gsip_process_file_py/README.md) | 把同一套工艺写成 Layer Builder 用的表格，以及如何核对 |
| 4 | [仿真](lumerical_simulations/ring_modulator/README.md) | 从耦合器到电路共七步，以及每一步的易错点 |
| 5 | [换成自己的工艺](docs/your_foundry.md) | 把流程搬到真实的代工厂 PDK 上，同时不泄露保密数据 |

微环调制器是按这套流程做完的第一个器件。其余的器件见下文的[器件库](#器件库)：目前有四个无源器件和一个热光移相器，各有一章教程，另外还有计划中的器件。

## 快速开始

需要 Python 3.12 或 3.13，以及 [uv](https://docs.astral.sh/uv/)。如果打算跑仿真，请把仓库放在不含中文等非 ASCII 字符的路径下，否则 Lumerical 求解器可能报错。

**版图和测试**（不需要 Lumerical）：

```bash
git clone https://github.com/q3430468220-tech/photonics-layout-cookbook.git
cd photonics-layout-cookbook
uv sync

uv run python gsip_technology.py                  # 列出图层和膜层堆叠，生成 KLayout 用的图层配色
uv run python devices/ring_modulator_builder.py   # 画微环调制器，跑 DRC，输出版图
uv run pytest                                     # 146 项测试
```

builder 最后会打印 `DRC passed: 0 errors, 0 warnings`，并输出 `devices/gds/ring_modulator.gds`。这个文件可以用免费的版图软件 [KLayout](https://www.klayout.de) 打开，图层配色在 `klayout_tech/layers.lyp`。[器件库](#器件库)里的每个器件在 `devices/` 下都有一个这样的 builder。

**图片**（不需要 Lumerical）。仿真结果已经保存在仓库里，第 4 章和各器件教程的每张图都可以直接重画。绘图脚本在各器件的 `figures/` 文件夹下，例如：

```bash
uv run python lumerical_simulations/ring_modulator/figures/fig2_passive.py
```

**仿真**（需要带 FDTD、MODE、CHARGE、HEAT 和 INTERCONNECT 的 Lumerical）。脚本会在常见的安装目录里找 Lumerical，装在别处时请设置 `LUMERICAL_ROOT`。各步按顺序运行，结果写进各自的文件夹，每一步做什么见第 4 章。注释里的时间是在作者的电脑上测的。

```bash
export LUMERICAL_ROOT=/opt/lumerical/v251        # PowerShell: $env:LUMERICAL_ROOT = "C:\Program Files\ANSYS Inc\v251\Lumerical"
uv run python gsip_process_file_py/gsip_process_file_compiler.py   # 可选：由 CSV 表格重新生成 gsip_process.lbr

cd lumerical_simulations/ring_modulator/scripts
uv run python layer_builder_check.py             # 第 0 步，约半分钟
uv run python coupling_coefficient_fdtd.py       # 第 1 步，约 30 分钟
uv run python passive_mode_fde.py                # 第 2 步，约 7 分钟
uv run python charge_profile.py                  # 第 3 步，约 9 分钟
uv run python heat_profile.py                    # 第 4 步，约 3 分钟
uv run python active_mode_fde.py                 # 第 5 步，约 1 分钟
uv run python ring_modulator_interconnect.py     # 第 6 步，不到 1 分钟
```

## PDK

<p align="center"><img src="assets/pdk_stack.png" width="100%" alt="教学工艺的截面图：按比例画出的完整膜层堆叠，以及放大的硅、锗和氮化硅层"></p>

*整套工艺的截面图：a 是按比例画出的完整膜层，b 是硅、锗和氮化硅这几层，纵向放大了五倍。底部深色字标出的是微环调制器用到的部分。*

这套 PDK 描述的是一个教学工艺。它沿用 Chrostowski 和 Hochberg 教材里的通用工艺，图层编号取自开源的 gdsfactory 通用 PDK。它不对应任何一家代工厂，其中的数值不能用于流片。商业代工厂的完整有源工艺都受保密协议约束，不能公开，所以教程自己定义了一套。

| 类别 | 图层及 GDS 编号（层号/数据类型） | 说明 |
|---|---|---|
| 硅 | `WG` 1/0、`SLAB150` 2/0、`SLAB90` 3/0 | 220 nm 芯层，150 nm 和 90 nm 平板层 |
| 离子注入 | `N` 20/0、`P` 21/0、`NP` 22/0、`PP` 23/0、`NPP` 24/0、`PPP` 25/0 | n 型和 p 型各有轻、中、重三档，5 × 10¹⁷ 至 5 × 10²⁰ cm⁻³ |
| 锗、氮化硅 | `GE` 5/0、`GEN` 26/0、`GEP` 27/0、`WGN` 34/0 | 500 nm 锗，350 nm 氮化硅 |
| 接触孔与金属 | `VIAC` 40/0、`M1` 41/0、`VIA1` 44/0、`M2` 45/0、`VIA2` 43/0、`M3` 49/0、`PADOPEN` 46/0 | 铝，三层金属 |
| 加热器 | `HEATER` 47/0 | 150 nm 氮化钛（TiN），10 Ω/sq |
| 沟槽 | `DEEPTRENCH` 4/0、`UNDERCUT` 6/0 | 端面深槽和隔热深槽；衬底底切 |

[gsip_technology.py](gsip_technology.py) 里的工艺数值都标了出处：[B] 教材，[BJ] 教材工艺所依据的 Baehr-Jones 等人的论文，[GF] gdsfactory 通用 PDK，[T] 本仓库自定的教学取值，旁边写了理由。

## 微环调制器

<p align="center"><img src="assets/ring_modulator_layout.png" width="100%" alt="微环调制器版图：整体，硅与注入，接触孔与加热器，金属 2，全部图层"></p>

*[ring_modulator_builder.py](devices/ring_modulator_builder.py) 画出的器件：a 是整体，b 到 d 各显示一组图层，e 是全部图层。*

器件是一个半径 10 µm 的脊形波导微环，旁边是一根总线波导。PN 结覆盖环的 240°，n 区在环内侧。TiN 加热器在芯层正上方，覆盖 270°。金属 2 引出到五个焊盘：PN 结用地、信号、地（G-S-G）三个，加热器用两个（H）。

| 参数 | 默认值 | 说明 |
|---|---|---|
| `radius` | 10 µm | 周长 62.83 µm |
| `width` | 0.5 µm | 芯层高 220 nm，两侧是 90 nm 平板层 |
| `gap` | 0.37 µm | 总线和环之间的间距，这个值对应临界耦合（见第 6 步） |
| `pn_angle` | 240° | 结长 41.89 µm，占环的 67% |
| `heater_angle` | 270° | 两端接触区之间的加热器长 44.72 µm，电阻 280 Ω |

同一个函数可以画其他尺寸。参数不满足设计规则时（比如半径小于 10 µm 的下限），它会报错并指出是哪条规则。在仓库根目录下运行：

```python
import gsip_technology as t          # 导入即激活 PDK
from devices import ring_modulator_builder as rm
from gsip_drc import run_drc

ring = rm.ring_modulator(radius=12, gap=0.40)
print(run_drc(ring).summary())       # DRC passed: 0 errors, 0 warnings
t.write_gds_for_lumerical(ring, "build/ring_r12.gds", cellname="ring_r12")
```

用 Lumerical 的脚本语言，三条命令就能把版图搭成结构。第 0 到 5 步都是这样开头的，由 [lumerical_simulations/flow.py](lumerical_simulations/flow.py) 里的 `add_layer_builder` 完成，所有器件的仿真共用这个函数。第 0 步载入整个器件，后面各步只载入自己要仿真的那一段。

```text
addlayerbuilder;
loadgdsfile("devices/gds/ring_modulator.gds");
loadprocessfile("gsip_process_file_py/gsip_process.lbr");
```

## 仿真结果

仿真分七步。第 0 步检查结构；第 1 到 5 步各算器件的一项特性，依次是耦合、波导模式、PN 结、加热器、调制；第 6 步把这些结果放进微环的电路仿真。这些是教学工艺的仿真结果，还没有和实测数据对比过。每一步的方法和局限见第 4 章。

### 第 0 步：结构检查

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig0_layer_builder.png" width="100%" alt="搭建出的结构的材料分布：两个竖直截面和四个水平截面"></p>

这一步先确认 Layer Builder 搭出来的结构对不对。图中是模式求解器看到的材料分布，两个竖直截面，四个水平截面。脚本还列出了十个位置的折射率，从衬底一直到金属 2，旁边标着那里应有的材料，十处全部吻合。

### 第 1 步：耦合（FDTD）

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig1_coupling.png" width="100%" alt="耦合区的光场，功率耦合系数随间距的变化，功率耦合系数随波长的变化"></p>

κ² 是从总线波导耦合进环的功率比例。它随间距指数下降，从 200 nm 时的 0.118 降到 500 nm 时的 0.0034，在这个范围内符合 κ² = 1.26 · exp(−gap / 84.8 nm)。网格加密后 κ² 变化 2%，这一步的精度大致就是这个水平。

### 第 2 步：波导模式（MODE）

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig2_passive.png" width="100%" alt="直波导和弯曲波导的模式，折射率随波长的变化，弯曲损耗随半径的变化，各模式随芯层宽度的变化"></p>

脊形直波导的有效折射率是 2.568，群折射率是 3.94。按环的 10 µm 半径弯曲后，有效折射率是 2.570，弯曲损耗小到求解器分辨不出。损耗要到半径小于 6 µm 才出现，所以 10 µm 的设计规则留有余量。自由光谱范围，也就是相邻谐振峰的间隔，是 9.7 nm。子图 e 显示 0.5 µm 宽的芯层并非严格单模：第二个 TE 模已经是导模，有效折射率只比平板模式高 0.011。

这一步对网格很敏感。用均匀的 20 nm 网格时，同一根弯曲波导在这一步较宽的仿真窗口里算出 2.5765，在第 5 步用的较窄窗口里算出 2.5693。原因是硅的表面没有落在网格线上，而网格线的位置又随窗口变化。现在脚本让每个硅表面都落在网格线上，两个窗口算出来都是 2.570。

### 第 3 步：PN 结（CHARGE）

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig3_charge.png" width="100%" alt="掺杂分布，两个偏压下的载流子，载流子剖面，电容，RC 带宽，掺杂核对"></p>

结电容从 0 V 时的 0.40 fF/µm 降到反偏 4 V 时的 0.21 fF/µm，0 V 时的串联电阻是 150 Ω。按 41.89 µm 的结长算，RC 带宽在 0 V 时是 64 GHz，反偏 4 V 时升到 131 GHz。子图 g 对比了求解器实际用到的掺杂和工艺表格，两者相差不到 0.5%。

### 第 4 步：加热器（HEAT）

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig4_heat.png" width="100%" alt="温度分布，竖直方向的温度剖面，温升随功率的变化，开启瞬态"></p>

加热器每毫瓦功率使芯层升温 2.35 K。如果没有 PN 结的电极，温升会是 2.98 K：电极的金属紧挨着加热器，带走了大约五分之一的热量。功率阶跃之后，芯层温度以约 10 µs 的时间常数稳定下来。脚本还核对了能量平衡：输入 10.00 mW，流入热沉的也是 10.00 mW。

### 第 5 步：调制（MODE）

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig5_active.png" width="100%" alt="折射率变化、损耗、V pi L 和谐振偏移随反向偏压的变化"></p>

把第 3 步的载流子分布和第 4 步的温度场代入模式求解器。反偏 4 V 时有效折射率变化 1.7 × 10⁻⁴，谐振波长移动 45 pm。由此得到 V_π·L = 1.8 V·cm，即半波电压与长度的乘积，越小越好。加热器每毫瓦移动 124 pm，也就是说 PN 结加 4 V 的效果相当于加热器的 0.36 mW。所以工作点由加热器来定，PN 结在工作点附近做调制。

### 第 6 步：电路中的微环（INTERCONNECT）

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig6_circuit.png" width="100%" alt="光谱，四个偏压下的谐振，透过率随偏压的变化，消光比和 Q 随间距的变化，四个加热功率下的谐振"></p>

第 1 到 5 步的结果成为 INTERCONNECT 里一个微环元件的参数。光在环里走一圈损耗 0.069 dB，其中波导占 0.014 dB，PN 结的自由载流子占 0.056 dB。κ² 等于一圈损耗掉的功率比例（0.0159）时，微环处于临界耦合，对应的间距是 371 nm，所以版图取 0.37 µm。在这个间距下，有载 Q 值是 31 000，仿真得到的消光比是 46 dB。谐振峰宽 50 pm，换成频率是 6 GHz，对应 26 ps 的光子寿命。结的 RC 带宽是这个 6 GHz 的十倍，所以限制调制器速度的是光子寿命，不是 PN 结。

## 局限

- 工艺模型是理想化的：侧壁垂直，每个注入区内掺杂均匀，金属全部按铝处理，TiN 用体材料参数。
- CHARGE 和 HEAT 用的是直波导的二维截面，只有模式求解器考虑了弯曲。
- 没有计入加热器和波导上方金属对光的吸收。
- 电路模型不含自热效应，也没有焊盘和走线的射频模型。
- 2.2 dB/cm 的波导损耗取自相近工艺的公开文献，不是仿真得到的。
- 网格精度：有效折射率约 5 × 10⁻⁴，κ² 约 2%。临界耦合附近的消光比对 κ² 非常敏感：κ² 大 1% 是 40 dB，小 1% 是 77 dB，而不是 46 dB。所以仿真只能说明谐振很深，给不出确切的深度。

## 换成自己的工艺

流程不变，要换的是工艺内容：`gsip_technology.py` 里的图层表、膜层堆叠和设计规则，以及 `gsip_process_file_py/gsip_csv/` 里的表格，后者按代工厂的设计手册来填。编译之后先跑第 0 步，再做其他步骤。[第 5 章](docs/your_foundry.md)按顺序讲了整个过程，以及每个阶段该拿什么来对照。代工厂的数据请放在私有仓库里，保密协议下拿到的内容不要进公开仓库。

[more_processes/cornerstone_soi220a/](more_processes/cornerstone_soi220a/README.md) 把同样的流程用在一条真实的开放工艺上。那条工艺只有一层金属，也没有专门的加热器层，做出来的器件相当不同。这个例子保持 v0.2 发布时的样子，v0.3 的修正还没有同步过去，具体缺哪些见它的 README。

## 器件库

微环调制器是器件库里的一个器件。库里的每个器件都是同样的做法：`devices/` 下一个用 PDK 画版图的 builder，一组把这份版图和工艺文件一起载入的仿真脚本，再加一章讲方法、结果和易错点的教程。器件教程的正文目前也是英文。

卡片右上角是实心圆点的，教程已经写好，点卡片就能打开。其余的还在计划中，点开是 [ROADMAP.md](ROADMAP.md) 里对应的条目。这些图是示意图，不是版图。

### 无源器件

GSiP 工艺的硅层和氮化硅层上的 12 个器件。前四个的教程已经写好，卡片下方的表格列出了各自的主要结果。

<p align="center">
<a href="lumerical_simulations/strip_waveguide/README.md" title="条形波导、弯曲和锥形"><img src="assets/device_library/passive/strip_waveguide.png" width="24%" alt="条形波导、弯曲和锥形"></a>
<a href="lumerical_simulations/rib_waveguide/README.md" title="脊形波导和弯曲"><img src="assets/device_library/passive/rib_waveguide.png" width="24%" alt="脊形波导和弯曲"></a>
<a href="lumerical_simulations/directional_coupler/README.md" title="定向耦合器"><img src="assets/device_library/passive/directional_coupler.png" width="24%" alt="定向耦合器"></a>
<a href="lumerical_simulations/mmi1x2/README.md" title="1×2 MMI 分束器"><img src="assets/device_library/passive/mmi1x2.png" width="24%" alt="1×2 MMI 分束器"></a>
<a href="ROADMAP.md#unit-devices-passive" title="2×2 MMI 耦合器"><img src="assets/device_library/passive/mmi2x2.png" width="24%" alt="2×2 MMI 耦合器"></a>
<a href="ROADMAP.md#unit-devices-passive" title="Y 分支"><img src="assets/device_library/passive/y_branch.png" width="24%" alt="Y 分支"></a>
<a href="ROADMAP.md#unit-devices-passive" title="交叉波导"><img src="assets/device_library/passive/waveguide_crossing.png" width="24%" alt="交叉波导"></a>
<a href="ROADMAP.md#unit-devices-passive" title="光栅耦合器"><img src="assets/device_library/passive/grating_coupler.png" width="24%" alt="光栅耦合器"></a>
<a href="ROADMAP.md#unit-devices-passive" title="端面耦合器"><img src="assets/device_library/passive/edge_coupler.png" width="24%" alt="端面耦合器"></a>
<a href="ROADMAP.md#unit-devices-passive" title="上下载型微环滤波器"><img src="assets/device_library/passive/ring_filter.png" width="24%" alt="上下载型微环滤波器"></a>
<a href="ROADMAP.md#unit-devices-passive" title="马赫-曾德尔干涉仪"><img src="assets/device_library/passive/mach_zehnder_interferometer.png" width="24%" alt="马赫-曾德尔干涉仪"></a>
<a href="ROADMAP.md#unit-devices-passive" title="氮化硅波导和层间过渡"><img src="assets/device_library/passive/sin_waveguide.png" width="24%" alt="氮化硅波导和层间过渡"></a>
</p>
<p align="center"><img src="assets/device_library/passive/legend.png" width="100%" alt="无源器件的配色说明"></p>

| 器件 | 求解器 | 1.55 µm、TE 光下的结果 |
|---|---|---|
| [条形波导、弯曲和锥形](lumerical_simulations/strip_waveguide/README.md) | MODE、EME | n_eff 2.444，n_g 4.24；半径 5 µm 的 90° 弯曲损耗 0.012 dB；20 µm 长、展宽到 3 µm 的锥形损耗 0.02 dB |
| [脊形波导和弯曲](lumerical_simulations/rib_waveguide/README.md) | MODE | n_eff 2.568，n_g 3.94；半径 10 µm 的 90° 弯曲损耗 0.046 dB |
| [定向耦合器](lumerical_simulations/directional_coupler/README.md) | MODE、FDTD | 间隙 0.2 µm、直波导段 15 µm 时分光 50:50，这个长度的精度约 0.3 µm；损耗 0.003 dB；分光比保持在 45:55 以内的带宽是 29 nm |
| [1×2 MMI 分束器](lumerical_simulations/mmi1x2/README.md) | EME、FDTD | 多模区 2.5 × 5.5 µm 时两路均分，损耗 0.085 dB；1500 到 1600 nm 内损耗 0.04 到 0.21 dB |

### 有源器件

用到同一套工艺里的注入、锗、加热器和金属的 8 个器件。本页讲的微环调制器是其中之一。热光移相器的教程也已经写好，卡片下方的表格列出了这两个器件的主要结果。

<p align="center">
<a href="lumerical_simulations/thermo_optic_phase_shifter/README.md" title="热光移相器"><img src="assets/device_library/active/thermo_optic_phase_shifter.png" width="24%" alt="热光移相器"></a>
<a href="ROADMAP.md#unit-devices-active" title="PN 移相器"><img src="assets/device_library/active/pn_phase_shifter.png" width="24%" alt="PN 移相器"></a>
<a href="ROADMAP.md#unit-devices-active" title="PIN 移相器和可变光衰减器"><img src="assets/device_library/active/pin_phase_shifter.png" width="24%" alt="PIN 移相器和可变光衰减器"></a>
<a href="lumerical_simulations/ring_modulator/README.md" title="微环调制器"><img src="assets/device_library/active/ring_modulator.png" width="24%" alt="微环调制器"></a>
<a href="ROADMAP.md#unit-devices-active" title="马赫-曾德尔调制器"><img src="assets/device_library/active/mach_zehnder_modulator.png" width="24%" alt="马赫-曾德尔调制器"></a>
<a href="ROADMAP.md#unit-devices-active" title="锗光电探测器"><img src="assets/device_library/active/ge_photodetector.png" width="24%" alt="锗光电探测器"></a>
<a href="ROADMAP.md#unit-devices-active" title="可调微环滤波器"><img src="assets/device_library/active/tunable_ring_filter.png" width="24%" alt="可调微环滤波器"></a>
<a href="ROADMAP.md#unit-devices-active" title="2×2 马赫-曾德尔光开关"><img src="assets/device_library/active/mzi_switch.png" width="24%" alt="2×2 马赫-曾德尔光开关"></a>
</p>
<p align="center"><img src="assets/device_library/active/legend.png" width="100%" alt="有源器件的配色说明"></p>

| 器件 | 求解器 | 1.55 µm、TE 光下的结果 |
|---|---|---|
| [热光移相器](lumerical_simulations/thermo_optic_phase_shifter/README.md) | HEAT、MODE | 带隔热槽时 π 相移需要 10.3 mW，不带槽时 22.0 mW；时间常数 18 µs，不带槽时 6 µs；槽外的相邻波导不再经氧化层受热 |
| [微环调制器](lumerical_simulations/ring_modulator/README.md) | FDTD、MODE、CHARGE、HEAT、INTERCONNECT | 间隙 371 nm 时临界耦合，有载 Q 为 31 000，消光比 46 dB；V_π·L 为 1.8 V·cm；加热器调谐 124 pm/mW |

### 薄膜铌酸锂电光器件

x 切薄膜铌酸锂（LNOI）上的 8 个电光器件。GSiP 工艺里没有铌酸锂，所以它们需要第二套教学工艺，和 GSiP 一样从公开文献的数值写起。这套工艺目前还没有。

<p align="center">
<a href="ROADMAP.md#unit-devices-thin-film-lithium-niobate" title="脊形波导和弯曲"><img src="assets/device_library/tfln/waveguide.png" width="24%" alt="脊形波导和弯曲"></a>
<a href="ROADMAP.md#unit-devices-thin-film-lithium-niobate" title="端面耦合器"><img src="assets/device_library/tfln/edge_coupler.png" width="24%" alt="端面耦合器"></a>
<a href="ROADMAP.md#unit-devices-thin-film-lithium-niobate" title="1×2 MMI 分束器"><img src="assets/device_library/tfln/mmi1x2.png" width="24%" alt="1×2 MMI 分束器"></a>
<a href="ROADMAP.md#unit-devices-thin-film-lithium-niobate" title="电光移相器"><img src="assets/device_library/tfln/eo_phase_shifter.png" width="24%" alt="电光移相器"></a>
<a href="ROADMAP.md#unit-devices-thin-film-lithium-niobate" title="马赫-曾德尔调制器"><img src="assets/device_library/tfln/mach_zehnder_modulator.png" width="24%" alt="马赫-曾德尔调制器"></a>
<a href="ROADMAP.md#unit-devices-thin-film-lithium-niobate" title="跑道型微环调制器"><img src="assets/device_library/tfln/racetrack_modulator.png" width="24%" alt="跑道型微环调制器"></a>
<a href="ROADMAP.md#unit-devices-thin-film-lithium-niobate" title="热光移相器"><img src="assets/device_library/tfln/thermo_optic_phase_shifter.png" width="24%" alt="热光移相器"></a>
<a href="ROADMAP.md#unit-devices-thin-film-lithium-niobate" title="2×2 电光开关"><img src="assets/device_library/tfln/eo_switch.png" width="24%" alt="2×2 电光开关"></a>
</p>
<p align="center"><img src="assets/device_library/tfln/legend.png" width="100%" alt="铌酸锂器件的配色说明"></p>

## 电路

电路由器件库里的器件搭成，用的是各器件章节保存下来的仿真结果，在 INTERCONNECT 里运行。电路分四个方向：可编程光子学、光计算、光互连和光交换。第一个电路是可编程干涉仪网格；光计算用的实数矩阵乘法器由两个这样的网格搭成。接下来是波分复用微环链路和光开关阵列（见 [ROADMAP.md](ROADMAP.md#circuits-and-links)）。

<p align="center"><img src="lumerical_simulations/clements_mesh/figures/fig0_layout.png" width="100%" alt="4×4 Clements 网格的版图：四列共六个干涉仪，十六个带隔热槽的加热器，三十二个焊盘"></p>

| 电路 | 由哪些器件组成 | 工具 | 1.55 µm、TE 光下的结果 |
|---|---|---|---|
| [Clements 网格，4×4](lumerical_simulations/clements_mesh/README.md) | 定向耦合器、热光移相器 | INTERCONNECT、Python | 任意幺正矩阵的保真度误差 1 − F 低于 10⁻⁶，加热器总功率约 160 mW；F > 0.99 的带宽 13 nm；相邻加热器的热串扰带来约 10⁻³ 的误差，拟合标定后可消除；耦合器间隙随机偏差 σ = 5 nm 时，拟合后所试的矩阵全部能实现 |
| [实数矩阵乘法器，4×4](lumerical_simulations/svd_multiplier/README.md) | 两个 Clements 网格和四个马赫-曾德尔衰减器 | INTERCONNECT、Python | 按奇异值分解实现任意实数矩阵，相对误差低于 5 × 10⁻¹³，加热器总功率约 335 mW；能设置的最小奇异值是最大值的 2 × 10⁻³；F > 0.99 的带宽 12 nm；作为神经网络的卷积层识别 1797 张手写数字测试图，准确率 97.3 %，每一张的识别结果都与电子网络相同；同样的卷积核若丢掉符号读出，准确率降到 56 % |

## 路线图

先做器件库里的单元器件，再做由它们组成的电路和链路。完整表格见 [ROADMAP.md](ROADMAP.md)。

| 方向 | 计划 |
|---|---|
| 可编程光子学 | 4×4 Clements 网格已[完成](lumerical_simulations/clements_mesh/README.md) |
| 光计算 | 4×4 实数矩阵乘法器已[完成](lumerical_simulations/svd_multiplier/README.md)；微环权重阵列（weight bank） |
| 光交换 | N×N 开关阵列：版图、损耗与串扰 |
| 光互联 | 波分复用发射端、解复用器和接收端：版图、链路预算、眼图 |

## 网站

教程还有一个网站版（英文）：<https://q3430468220-tech.github.io/photonics-layout-cookbook/>。网站展示的章节和结果与本仓库相同。

## 仓库结构

```text
photonics-layout-cookbook/
├── gsip_technology.py        PDK：图层、膜层堆叠、截面、设计规则
├── gsip_drc.py               设计规则检查
├── devices/                  每个器件或电路一个 builder，以及它们输出的版图（gds/）
├── gsip_process_file_py/     工艺表格（CSV）、编译脚本、编译好的 gsip_process.lbr
├── lumerical_simulations/
│   ├── flow.py               所有仿真共用的部分：路径和 Layer Builder 的搭建
│   ├── solvers.py            MODE、EME、FDTD、HEAT 的求解器配方
│   ├── panels.py             多个器件共用的绘图面板
│   └── <器件或电路>/         scripts/、每一步的结果文件夹、figures/、README.md
├── docs/                     第 1、2、5 章
├── assets/                   本页的图片；器件库的图块
├── tests/                    PDK、版图、DRC、连通性、工艺表格、图片
├── more_processes/           同一套流程在 CORNERSTONE SOI220A 上的实现
├── figstyle.py               统一的绘图风格
├── lumerical_env.py          查找 Lumerical 并导入 lumapi
└── klayout_tech/             KLayout 的图层配色
```

## 参与和许可

欢迎贡献，见 [CONTRIBUTING.md](CONTRIBUTING.md)。如果这份教程对你的研究或教学有帮助，请按 [CITATION.cff](CITATION.cff) 引用。代码采用 [MIT 许可](LICENSE)。

设计流程图里有三个图标取自研讨会幻灯片，不在 MIT 许可范围内。网站的设计、DARK MODE 这个名称及其标志也不在此列，它们不属于本仓库。本项目与 Ansys、Tower Semiconductor、CORNERSTONE、教材作者及 gdsfactory 团队均无隶属或背书关系。“Ansys”和“Lumerical”是 ANSYS, Inc. 的商标。

## 参考资料

- L. Chrostowski and M. Hochberg, *Silicon Photonics Design: From Devices to Systems*, Cambridge University Press, 2015, [doi:10.1017/CBO9781316084168](https://doi.org/10.1017/CBO9781316084168)
- T. Baehr-Jones et al., "A 25 Gb/s Silicon Photonics Platform", [arXiv:1203.0767](https://arxiv.org/abs/1203.0767)
- M. Nedeljkovic, R. Soref and G. Z. Mashanovich, "Free-carrier electrorefraction and electroabsorption modulation predictions for silicon over the 1–14 µm infrared wavelength range", IEEE Photonics Journal 3, 1171 (2011), [doi:10.1109/JPHOT.2011.2171930](https://doi.org/10.1109/JPHOT.2011.2171930)
- gdsfactory：[代码仓库](https://github.com/gdsfactory/gdsfactory)、[文档](https://gdsfactory.github.io/gdsfactory/)
- SiEPIC-Tools（含 GSiP 库）：[代码仓库](https://github.com/SiEPIC/SiEPIC-Tools)
- Ansys Optics：[Layer builder](https://optics.ansys.com/hc/en-us/articles/360034382394-Layer-builder-Simulation-object)、[Ring Modulator](https://optics.ansys.com/hc/en-us/articles/360042322794-Ring-Modulator)、[Workshop: Designing Foundry-Compatible Photonic Components and Circuits](https://optics.ansys.com/hc/en-us/articles/31257798958611-Workshop-Designing-Foundry-Compatible-Photonic-Components-and-Circuits)
- CORNERSTONE：[开放 PDK 仓库](https://github.com/cornerstone-uos/cornerstone-pdk)
