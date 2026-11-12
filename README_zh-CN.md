# photonics-layout-cookbook

**一套与代工厂工艺兼容的硅光设计流程，在一个公开的有源 PDK 上完整走通：从 gdsfactory 工艺定义文件，到器件版图、Lumerical 工艺文件，再到带热调的微环调制器的器件级和电路级仿真。**

[English](README.md) | [简体中文](README_zh-CN.md)

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)
![gdsfactory](https://img.shields.io/badge/layout-gdsfactory%209-6f42c1)
![lumerical](https://img.shields.io/badge/simulation-Ansys%20Lumerical-orange)
![foundry](https://img.shields.io/badge/process-CORNERSTONE%20SOI220A-2f8f5b)

多数同学学仿真微环调制器时，结构是在仿真软件里画的，层叠是手工填的。代工厂的做法正好相反：工艺是固定的，
你交出去的只有版图，仿真必须描述“这份版图在这个工艺里会变成什么”。本仓库在一个数据公开的工艺上，把这条
流程从头到尾走了一遍。

<p align="center">
  <img src="assets/design_flow.svg" width="100%" alt="设计流程：公开的代工厂数据、工艺定义文件、器件生成器、工艺文件、Layer Builder、六步仿真">
</p>

同一份公开资料把工艺描述了两次：一次给版图用（gdsfactory PDK），一次给仿真用（Lumerical Layer Builder
工艺文件）。器件用前者画，用后者仿真。任何一个仿真脚本里都没有厚度、材料或掺杂浓度。

## 流程的五个部分

| 部分 | 文件 | 作用 |
|---|---|---|
| 工艺定义 | [cornerstone_technology.py](cornerstone_technology.py) | 把代工厂工艺写成 gdsfactory PDK：官方层名、设计规则、层叠、波导截面。 |
| 设计规则检查 | [cornerstone_drc.py](cornerstone_drc.py) | 按公开的规则检查版图，纯 Python，不需要打开 KLayout。 |
| 器件 | [rm_builder.py](rm_builder.py) | 用 PDK 截面画出微环调制器，自检并写出 GDS。 |
| 工艺文件 | [cornerstone_process_file_py/](cornerstone_process_file_py/) | 同一工艺的 CSV 表，通过 `lumapi` 编译成 `cornerstone_process.lbr`。 |
| 仿真 | [lumerical_simulations/ring_modulator/](lumerical_simulations/ring_modulator/) | 六个步骤，覆盖 FDTD、MODE、CHARGE、HEAT 和 INTERCONNECT，每步都载入 GDS 和 `.lbr`。 |

## 工艺：CORNERSTONE SOI 220 nm 有源平台

[CORNERSTONE](https://www.cornerstone.sotonfab.co.uk/) 是南安普顿大学的开源、免许可硅光代工平台。它的有源
平台 `SOI220A` 提供三次硅刻蚀、四次注入和一层金属。本仓库用到的全部数据来自两份公开资料：

- 官方 PDK 仓库 [cornerstone-uos/cornerstone-pdk](https://github.com/cornerstone-uos/cornerstone-pdk) 的 `SOI220A` 目录：层名与层号、单层规则、截面、标准器件；
- [220 nm SOI 有源 MPW 第 47 次流片的设计指南](https://cornerstone.sotonfab.co.uk/wp-content/uploads/2025/10/CORNERSTONE-47th-Call-Design-Guidelines_final-1.pdf)：工艺流程、掺杂、层间规则、掩膜处理。

| GDS | 官方层名 | 含义 |
|---|---|---|
| 3/0 | `Si_Etch2_LF_120nm` | 波导芯，画出的图形保留完整的 220 nm |
| 5/0 | `Si_Etch3_LF_100nm_to_BOX` | 脊形保护层，画出的图形保留 100 nm slab |
| 6/0 | `Si_Etch1_DUV_DF_70nm` | 光栅耦合器，刻蚀 70 nm |
| 7/0、8/0 | `P_Implant_Low_DF`、`N_Implant_Low_DF` | 形成 PN 结的低剂量注入 |
| 9/0、11/0 | `P_Implant_Hi_DF`、`N_Implant_Hi_DF` | 欧姆接触用的高剂量注入 |
| 12/0 | `Via_DF` | 穿过上包层的通孔 |
| 13/0 | `Electrode_LF` | 铝电极、焊盘和加热丝 |

这个工艺有三个特点直接决定了器件的样子，代码对每一个都做了建模：

- **只有一层金属。** 加热器画在电极层上。结电极和加热器因此要分享环的周长：PN 结占上方 240°，加热器占下方 76°。
- **自对准的 n 型注入。** 它从脊的侧壁进入，深约 110 nm，与掩膜边缘画在芯内的哪个位置无关。结的位置不在掩膜边缘处。
- **代工厂会处理掩膜。** 波导两侧的沟槽由代工厂生成，高剂量注入区会被并入 slab。工艺文件复现了这些处理。

每个数值的出处，以及公开资料之间不一致的地方，见
[cornerstone_csv/README.md](cornerstone_process_file_py/cornerstone_csv/README.md)。

## 完整算例

<p align="center">
  <img src="assets/rm_ring.png" width="49%" alt="微环调制器版图：上方 GSG 焊盘接 PN 结，下方两个焊盘接加热器">
  <img src="assets/rm_ring_zoom.png" width="49%" alt="环、耦合区、掺杂段和加热器">
</p>

半径 25 µm 的脊形微环，点耦合。上方的 GSG 焊盘驱动 PN 结段，下方两个焊盘给未掺杂段上方的加热器供电。

| 结果 | 数值 | 来自 |
|---|---|---|
| 功率耦合系数 | κ² = 3.73 · exp(−gap / 101.6 nm) | 第 1 步，FDTD |
| 有效折射率与群折射率 | 2.5515 与 3.912 | 第 2 步，MODE |
| 0 V 与 −4 V 的结电容 | 0.43 与 0.22 fF/µm | 第 3 步，CHARGE |
| 加热效率 | 加热段内 1.37 K/mW | 第 4 步，HEAT |
| −2 V 的调制效率 VπL | 1.4 V·cm | 第 5 步，MODE |
| 临界耦合间距 | 425 nm | 第 6 步，INTERCONNECT |
| 负载 Q 与自由光谱范围 | 20 900 与 3.90 nm | 第 6 步 |
| −4 V 的谐振漂移 | 50 pm | 第 6 步 |
| 热调谐 | 17.1 pm/mW | 第 6 步 |

<p align="center">
  <img src="lumerical_simulations/ring_modulator/plots/6_interconnect_ring_modulator/ring_modulator.png" width="100%" alt="消光比随间距的变化、不同结偏压下的谱、不同加热功率下的谱">
</p>

第 6 步给出临界耦合所需的间距，这个值就是版图的默认间距。每一步的方法、关键设置和局限写在
[lumerical_simulations/ring_modulator/README.md](lumerical_simulations/ring_modulator/README.md)。
以上都是仿真结果，没有和流片器件对比过。

## 快速开始

版图、DRC 和测试只需要 Python。工艺文件和仿真需要 Ansys Lumerical。

```bash
# 1. 环境（uv：https://docs.astral.sh/uv/）
git clone https://github.com/q3430468220-tech/photonics-layout-cookbook.git
cd photonics-layout-cookbook
uv sync

# 2. PDK：列出图层，写出 KLayout 工艺包
uv run python cornerstone_technology.py

# 3. 器件：GDS、DRC 报告、预览图
uv run python rm_builder.py

# 4. 工艺文件（需要 Lumerical 的 FDTD 和 CHARGE 许可）
uv run python cornerstone_process_file_py/cornerstone_process_file_compiler.py

# 5. 六步仿真
cd lumerical_simulations/ring_modulator/scripts
uv run python coupling_coefficient_fdtd.py --dry   # 先用粗网格验证，其余步骤见该目录的 README

# 测试与代码检查（不需要 Lumerical）
uv run pytest
uv run ruff check .
```

Lumerical 的位置通过环境变量 `LUMERICAL_ROOT` 指定，不设置时会到常见安装路径里找：

```bash
# PowerShell
$env:LUMERICAL_ROOT = "C:\Program Files\ANSYS Inc\v251\Lumerical"
# bash
export LUMERICAL_ROOT=/opt/lumerical/v251
```

请把仓库放在不含中文等非 ASCII 字符的路径下，否则 Lumerical 求解器可能失败。

### 在自己的脚本里使用

```python
import gdsfactory as gf
import cornerstone_technology as t  # 导入即激活 PDK
import rm_builder as rm
from cornerstone_drc import run_drc

phase_shifter = gf.components.straight(length=500, cross_section="rib_1550nm_TE_pn")
ring = rm.ring_modulator(radius=30, gap=0.40)

assert run_drc(ring).passed
t.write_gds_for_lumerical(ring, "ring.gds")  # 展平，并带上工艺文件需要的仿真层
```

在 Lumerical 里用脚本或 Layer Builder 对话框载入：

```text
addlayerbuilder;
loadgdsfile("ring.gds");
loadprocessfile("cornerstone_process.lbr");
```

## 目录结构

```text
photonics-layout-cookbook/
├── cornerstone_technology.py        PDK：图层、规则、层叠、截面、单元
├── cornerstone_drc.py               设计规则检查（klayout.db）
├── rm_builder.py                    微环调制器版图
├── rm_ring.gds                      它的输出，可直接导入 Layer Builder
├── lumerical_env.py                 定位 Lumerical 并导入 lumapi
│
├── cornerstone_process_file_py/
│   ├── cornerstone_process_file_compiler.py   CSV 表 → .lbr，带回读核对
│   ├── cornerstone_process.lbr                编译好的工艺文件
│   └── cornerstone_csv/                       层叠、掺杂、材料、工艺偏差，以及说明文档
│
├── lumerical_simulations/ring_modulator/
│   ├── scripts/                     common.py 和每步一个脚本
│   ├── 1_coupling_coefficient/ … 6_interconnect_ring_modulator/   版图与结果摘要
│   ├── plots/                       每步的绘图脚本和图
│   └── README.md                    每步的方法、结果和注意事项
│
├── klayout_tech/                    KLayout 用的 layers.lyp 和 tech.lyt
├── assets/                          本 README 的图
├── tests/                           pytest：PDK、版图、DRC、工艺表
└── legacy/                          v0.1 的旧代码，仅作参考
```

## 把流程换到另一个工艺

1. 复制 `cornerstone_technology.py`，替换其中的常数、层表、规则和截面。层名沿用代工厂自己的命名。
2. 复制 `cornerstone_csv/`，按同一批文档填表。每个数值都标注出处，手册没给、自己假设的要明确标出来。
3. 运行编译脚本。它会回读 `.lbr` 并和表格逐项核对。
4. 先在 MODE 里核对一个已知截面，再做别的。层表达式写错时，有效折射率会明显不对。
5. 公开仓库只放公开数据。签了保密协议拿到的 PDK 绝对不要提交。

## 局限与声明

- 这些数值用于教学和搭建仿真。流片前，所有数值都要以你所投那一次流片的设计指南为准，并运行代工厂自己的 DRC。
- 有几项输入是假设值，文中都有标注：侧壁角、注入的深度分布、铝的电阻率、上包层是平的。
- 公开资料对氧化层厚度的说法不一致。本仓库采用设计指南的值，对照表见
  [cornerstone_csv/README.md](cornerstone_process_file_py/cornerstone_csv/README.md)。
- 代码基于 gdsfactory 9.5x 和 Lumerical 2025 R1 编写。
- 本项目与 CORNERSTONE、南安普顿大学、Ansys 和 gdsfactory 团队没有隶属或背书关系。“Ansys”和“Lumerical”是 Ansys, Inc. 的商标。

## 路线图、贡献与引用

接下来计划：由这六步生成紧凑模型，在同一工艺上增加更多器件，以及接入第二个公开工艺，见 [ROADMAP.md](ROADMAP.md)。
欢迎贡献，尤其是新器件和新的公开工艺，见 [CONTRIBUTING.md](CONTRIBUTING.md)。如果本仓库对你的研究或教学有帮助，
请通过 [CITATION.cff](CITATION.cff) 引用。代码以 [MIT 许可](LICENSE) 发布。

## 参考

- CORNERSTONE，[公开 PDK 仓库](https://github.com/cornerstone-uos/cornerstone-pdk) 与 [220 nm SOI 有源 MPW 第 47 次流片设计指南](https://cornerstone.sotonfab.co.uk/wp-content/uploads/2025/10/CORNERSTONE-47th-Call-Design-Guidelines_final-1.pdf)
- Ansys Optics，[Layer builder - Simulation object](https://optics.ansys.com/hc/en-us/articles/360034382394-Layer-builder-Simulation-object)
- Ansys Optics，[Ring Modulator](https://optics.ansys.com/hc/en-us/articles/360042322794-Ring-Modulator)
- Ansys Optics，[Workshop: Designing Foundry-Compatible Photonic Components and Circuits](https://optics.ansys.com/hc/en-us/articles/31257798958611-Workshop-Designing-Foundry-Compatible-Photonic-Components-and-Circuits)
- gdsfactory，[文档](https://gdsfactory.github.io/gdsfactory/)
