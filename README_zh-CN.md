# photonics-layout-cookbook（光子芯片版图菜谱）

**用 [gdsfactory](https://github.com/gdsfactory/gdsfactory) 画硅光版图：基于开源代工厂 PDK，从单元器件到功能模块再到系统架构，并且版图可以无缝导入 Ansys Lumerical 仿真。**

[English](README.md) | [简体中文](README_zh-CN.md)

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)
![gdsfactory](https://img.shields.io/badge/layout-gdsfactory-6f42c1)
![lumerical](https://img.shields.io/badge/simulation-Ansys%20Lumerical-orange)
![status](https://img.shields.io/badge/status-v0.1%20alpha-lightgrey)

很多硅光方向的同学会用 Lumerical 仿真微环调制器，却从来没画过一张能交给代工厂的版图：版图往往靠拷贝师兄师姐的 GDS 学，代工厂 PDK 又要签保密协议，仿真模型和真实版图之间也常常是“两张皮”。这个项目反过来教版图：每个器件都是一段简短、可读的 **gdsfactory 菜谱**，画在一个 **开源代工厂工艺** 上，生成的 GDS 可以 **直接导入 Lumerical**（FDTD、MODE、CHARGE），一个尺寸都不用手抄。

<p align="center">
  <img src="docs/images/ring_modulator_top.png" width="92%" alt="CORNERSTONE 220 nm SOI 上的 PN 微环调制器"><br>
  <img src="docs/images/ring_modulator_xsec.png" width="80%" alt="从版图中提取的 CHARGE / FDE 截面"><br>
  <em>菜谱 01：CORNERSTONE 220 nm SOI 上的横向 PN 微环调制器（上），以及桥接工具从 GDS 中自动提取、用于 CHARGE 和 MODE-FDE 的截面（下）。</em>
</p>

## 项目包含什么

项目分成三个严格解耦的部分，每一部分都可以单独学习、单独替换。

**菜谱（器件绘制）**（`src/photonics_cookbook/devices`、`cells.py`、`examples/`）：器件画在 *图层角色* 上，比如 `core`（全厚度硅）、`slab`（平板区）、`n`、`ppp`（P++）、`via`、`metal`，而不是直接写死 GDS 层号。单元器件的平面尺寸参照 Ansys Lumerical 官方应用案例，方便你把自己的仿真结果和官方文件对照。

**工艺适配器**（`src/photonics_cookbook/process/data/*.yaml`）：把这些角色映射到具体代工厂，包括 GDS 层号/数据类型、纵向叠层、Lumerical 材料名、掺杂类型和浓度。把一个器件迁移到另一家代工厂只需要写一个 YAML 文件，不用改器件代码。第一个适配的是开放的 [CORNERSTONE](https://www.cornerstone.sotonfab.co.uk/)（南安普顿大学）220 nm SOI 有源工艺，运行时会和 gdsfactory 官方的 [`cspdk`](https://github.com/gdsfactory/cspdk) 自动核对层号。

**Lumerical 桥接**（`src/photonics_cookbook/lumerical`）：只读取 GDS 和工艺文件，就能生成可直接运行的 Lumerical 脚本。因为它不依赖 Python 对象，所以用 KLayout 手画的版图、代工厂 PCell 生成的版图同样适用。

| 生成的脚本 | Lumerical 模块 | 作用 |
|---|---|---|
| `<cell>_geometry3d.lsf` | FDTD / MODE | 对每个绘制图层执行 `gdsimport`（带 z 范围和材料），并加上埋氧层/包层 |
| `<cell>_fdtd3d.lsf` | FDTD | 几何 + 按光学层自动确定的 3D FDTD 区域 + 与 gdsfactory 光端口一一对应的 port |
| `<cell>_layerbuilder.lsf` | FDTD / MODE | 用脚本搭建 Layer Builder，再让 Lumerical 自己写出该工艺的 `.lbr` 文件 |
| `<cell>_charge2d.lsf` | CHARGE | 沿切线截取版图：硅、注入区、通孔作为电极、偏压扫描、载流子分布导出 |
| `<cell>_fde2d.lsf` | MODE（FDE） | 同一切线、同一坐标系；导入 CHARGE 载流子，扫描偏压，给出 Δn_eff、损耗、pm/V |

```mermaid
flowchart LR
    A["菜谱<br/>(gdsfactory cell)"] --> B["GDS"]
    P["工艺 YAML<br/>角色→层号、叠层、<br/>材料、掺杂"] --> C
    B --> C{"Lumerical 桥接"}
    C --> D["FDTD 3D<br/>gdsimport / Layer Builder"]
    C --> E["CHARGE 2D<br/>切线→掺杂、电极"]
    E -- "n, p (.mat)" --> F["MODE FDE 2D<br/>Δn_eff、损耗 vs 电压"]
    D --> G["INTERCONNECT / CML<br/>（规划中）"]
    F --> G
```

## 快速开始

项目使用 [uv](https://docs.astral.sh/uv/) 管理可复现的 Python 环境。

```bash
# 1. 安装 uv（只需一次）        Windows PowerShell:  irm https://astral.sh/uv/install.ps1 | iex
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 获取代码并建立环境（Python 3.12、gdsfactory、cspdk、klayout 等）
git clone https://github.com/q3430468220-tech/photonics-layout-cookbook.git
cd photonics-layout-cookbook
uv sync                     # 自动创建 .venv 并生成 uv.lock

# 3. 检查环境，认识代工厂 PDK
uv run python examples/00_getting_started/00_check_environment.py
uv run photonics-cookbook show-process cornerstone_si220_active
uv run photonics-cookbook check-pdk cornerstone_si220_active

# 4. 菜谱 01：画微环调制器，并导出到 Lumerical
uv run python examples/01_devices/01_ring_modulator/01_layout.py
uv run python examples/01_devices/01_ring_modulator/02_export_to_lumerical.py

# 5.（可选，需要本机安装 Lumerical 和许可证）通过 lumapi 依次运行 CHARGE -> MODE
#    PowerShell: $env:LUMERICAL_ROOT="C:\Program Files\ANSYS Inc\v251\Lumerical"
uv run python examples/01_devices/01_ring_modulator/03_run_lumerical.py

# 测试与代码检查
uv run pytest
uv run ruff check .
```

国内网络下载慢时，可以给 uv 配置 PyPI 镜像，例如 `uv sync --default-index https://pypi.tuna.tsinghua.edu.cn/simple`，或设置环境变量 `UV_DEFAULT_INDEX`。uv 首次运行会自动下载 Python 3.12，如果这一步也很慢，可以先自行安装 Python 3.12，uv 会直接使用它。

输出文件在 `build/` 目录（已被 git 忽略）。**Lumerical 求解器在包含中文等非 ASCII 字符的路径下可能无法写入临时数据文件**（典型报错是 `failed to open data file ...~#xxx.data`）。如果仓库放在中文路径下，请用环境变量把输出目录指到纯英文路径，例如 `PHOTONICS_BUILD_DIR=D:\photonics_build`。查看版图请安装 [KLayout](https://www.klayout.de/) 直接打开 GDS，或者安装 KLayout 的 `klive` 插件后在 Python 里调用 `c.show()`。

## 目录结构

```text
photonics-layout-cookbook/
├── pyproject.toml / .python-version     uv 项目（Python 3.12）
├── src/photonics_cookbook/
│   ├── process/                         代工厂工艺适配器
│   │   ├── model.py                     角色、叠层、材料、掺杂（含校验）
│   │   ├── upstream.py                  与 gdsfactory PDK 核对 / 从 PDK 生成草稿
│   │   └── data/cornerstone_si220_active.yaml, _template.yaml
│   ├── geometry.py                      与工具无关的多边形 + 端口
│   ├── devices/ring_modulator.py        器件几何计算（纯 Python，有单元测试）
│   ├── cells.py                         gdsfactory 单元（@gf.cell）
│   ├── lumerical/                       GDS -> Lumerical 桥接
│   │   ├── gds_reader.py  cutline.py    读取 GDS（KLayout）、提取二维截面
│   │   ├── scripts_3d.py  scripts_2d.py FDTD / Layer Builder / CHARGE / FDE 脚本生成
│   │   ├── export.py                    export_lumerical()：一次调用生成全部脚本
│   │   └── runner.py                    通过 lumapi 运行脚本
│   ├── plotting.py  cli.py  paths.py
├── examples/
│   ├── 00_getting_started/
│   └── 01_devices/01_ring_modulator/    01_layout → 02_export → 03_run_lumerical
├── docs/                                lumerical-bridge.md、process-adapters.md、images/
├── tests/                               pytest（未安装 gdsfactory 时相关测试自动跳过）
└── ROADMAP.md  CONTRIBUTING.md  LICENSE
```

## 学习路线（Roadmap）

内容按三个层级逐步更新。每个菜谱都包含版图、Lumerical 导出脚本和设计思路说明。完整计划（以及每个器件对应哪个 Ansys 官方案例）见 [ROADMAP.md](ROADMAP.md)。

| 层级 | 菜谱 | Lumerical 仿真链 | 状态 |
|---|---|---|---|
| 1 · 单元器件 | 微环调制器（横向 PN 结） | CHARGE → FDE → FDTD 耦合区 → INTERCONNECT | **v0.1** |
| | PN 耗尽型移相器、行波 MZM | CHARGE → FDE、行波电极 | 规划中 |
| | PIN 移相器 / MZM、热光移相器 | CHARGE / HEAT → FDE | 规划中 |
| | 锗探测器（垂直 / 横向） | FDTD → CHARGE | 规划中 |
| | 无源器件：光栅/端面耦合器、MMI、定向耦合器、Y 分支 | FDTD / EME / varFDTD | 规划中 |
| 2 · 功能模块 | MZI 单元 → Clements / Reck N×N 网络 | INTERCONNECT 网表 | 规划中 |
| | 上下载微环滤波器、高阶微环滤波器、WDM 复用/解复用 | FDTD + INTERCONNECT | 规划中 |
| 3 · 系统架构 | WDM 光互连链路、MZI 光交换阵列、光 I/O（OIO）芯粒 | INTERCONNECT | 规划中 |

接下来计划适配的代工厂/PDK：SiEPIC EBeam（`ubcpdk`）、gdsfactory 通用 PDK、VTT 3 µm SOI、Luxtelligence 薄膜铌酸锂。

## 设计原则

GDS 是“契约”：下游的一切（Lumerical、DRC、其他工具）只读取 GDS 和工艺文件，不依赖 Python 对象。器件代码只用图层角色，不写死层号，代工厂相关知识只存在于一个地方。每个数字都有出处：工艺文件注明来源的公开设计文档，器件默认参数注明参照的 Ansys 案例。版图天生“可仿真”：每个单元都把仿真需要的提示（切线位置、弯曲半径、掺杂长度、电极所在层）存进 `component.info`。

## 当前状态与局限

目前是 alpha 版本。3D `gdsimport`、CHARGE 和 FDE 三条路线只用到官方文档中的脚本命令；Layer Builder 路线标记为实验性，因为它的部分属性名在不同 Lumerical 版本之间有差异（所有不确定的调用都包在 `try` 里并会打印提示）。生成的脚本面向 Lumerical 2022 R1 及以上版本。如果脚本报错，欢迎附上你的 Lumerical 版本号提 issue。

## 免责声明

工艺文件中的层号、叠层和掺杂数据来自代工厂公开资料，仅用于教学和仿真设置。**正式流片前，务必以你所投片批次的设计手册和 PDK 为准。** 本项目与 Ansys、CORNERSTONE / 南安普顿大学以及 gdsfactory 团队无隶属或背书关系。“Ansys”和“Lumerical”是 Ansys, Inc. 的商标。

## 参与贡献、引用与许可证

非常欢迎贡献，尤其是新的器件菜谱和新的代工厂适配器，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。如果本项目对你的科研或教学有帮助，请通过 [CITATION.cff](CITATION.cff) 引用。代码以 [MIT 许可证](LICENSE) 发布。

本项目基于 [gdsfactory](https://github.com/gdsfactory/gdsfactory)、[cspdk](https://github.com/gdsfactory/cspdk)、[KLayout](https://www.klayout.de/) 和 [Ansys Optics 应用案例库](https://optics.ansys.com/hc/en-us) 构建。
