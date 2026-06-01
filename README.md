# HyperPlot 使用说明书

HyperPlot 是一个面向 CSV 曲线数据的轻量绘图工具，包含两个入口：

- `PlotCSV_GUI.py`：图形界面，支持拖拽 CSV/SVG/PNG/模板文件。
- `HyperPlot.py`：后端绘图和状态管理模块，负责读数据、绘图、模板、SVG/PNG 元数据、背景包络等功能。

推荐日常使用 GUI；需要批处理时可以直接调用 `HyperPlot.HyperPlot`。

## 快速开始

启动 GUI：

```bash
python3 PlotCSV_GUI.py
```

基本流程：

1. 将一个或多个 `.csv` 文件拖入窗口。
2. 在左侧 `Workbench` 选择要绘制的曲线。
3. 在 `Batch Style` 输入批量曲线样式，或右键单条曲线单独编辑。
4. 点击 `Plot` 预览。
5. 在 `Output Filename` 输入文件名，或留空自动使用时间戳。
6. 点击 `Output` 导出图像。

如果输出文件名不带扩展名，会默认补成 `.svg`。

## CSV 输入格式

CSV 的第一列作为 x 轴数据，后续每一列都会成为一条 `PlotElement`。

例如：

```csv
strain,stress,temp
0.0,0.0,20.0
0.1,12.3,21.2
0.2,25.1,22.8
```

会生成两条曲线：

- `strain` - `stress`
- `strain` - `temp`

CSV 分隔符由 Properties 里的 `seperator` 控制。注意这个属性名目前沿用代码里的拼写 `seperator`。

## Workbench

`Workbench` 显示当前已经导入的所有曲线，格式大致为：

```text
file.csv | x_label | curve_label | line_style | (Left Axis)
```

如果曲线被设为背景，会额外显示 `[BG]`。

标题右侧按钮：

- `All`：当前没有全选时执行全选；已经全选时清空选择。
- `Invert`：反选当前 Workbench 选择。

右键菜单：

- `Edit Curve...`：单独编辑曲线 legend、style 和左右轴。
- `Delete Selected`：删除选中的曲线。
- `Set as Background`：把选中曲线设为同一个背景组。
- `Unset Background`：取消选中曲线的背景状态。

`Toggle Axis` 按钮会在左轴和右轴之间切换选中的曲线。

如果编辑的是背景组成员，`Edit Curve...` 会作用到整个背景组，因为背景组在最终图里是一个包络对象。

## Batch Style

`Batch Style` 用于按顺序批量设置当前选中绘图对象。它用 `|` 分隔多个绘图对象，每一项格式为：

```text
legend==style
```

例如：

```text
Experiment==-ro|Simulation==--b
```

含义：

- 第一条绘图对象 legend 为 `Experiment`，样式为红色实线加圆点。
- 第二条绘图对象 legend 为 `Simulation`，样式为蓝色虚线。

如果只写 legend：

```text
Experiment|Simulation
```

则只改 legend，不改线型。

### Matplotlib 样式简表

常用线型：

```text
-   实线
--  虚线
-.  点划线
:   点线
```

常用 marker：

```text
o   圆点
s   方块
^   三角
x   叉号
```

组合示例：

```text
Exp==-ro     红色实线加圆点
Model==--b   蓝色虚线
Data==mo     粉色圆点，无连线
```

## 自定义色板

Properties 里有 `color_palette`，可以覆盖短颜色码。

GUI 左侧 `Batch Style` 输入框下方会显示当前有效色板预览。每个色块上的字母就是 Batch Style 里使用的短颜色码。

默认色板为偏 Nature/Science 风格：

```text
b = #4dbbd5
g = #00a087
r = #e64b35
c = #3c5488
m = #cc79a7
y = #f39b7f
k = black
w = white
```

例如 `r` 是 `#e64b35` 后：

```text
Exp==ro
```

表示使用 `#e64b35` 的圆点。

如果要修改颜色：

1. 在 Properties 展开 `color_palette`。
2. 右键对应颜色键，例如 `r`。
3. 选择 `Edit Property`。
4. 输入新的颜色，例如 `#d62728`。

也可以在 `color_palette` 下插入新的键值。没有覆盖的颜色码会使用默认色板。

## 背景包络

背景功能用于把一组实验曲线显示成半透明范围，类似实验数据的 min-max envelope。

使用方法：

1. 在 Workbench 选中多条实验曲线。
2. 右键选择 `Set as Background`。
3. 再选中背景曲线和模拟曲线一起绘图。

背景组在最终图中算作一个绘图对象，所以 Batch Style 只需要写一项：

```text
Experimental range==b|Simulation==-r
```

如果背景组里有多条曲线，HyperPlot 会：

1. 找到所有曲线共同覆盖的 x 范围。
2. 插值到统一的 `background_points` 网格。
3. 计算 `y_min` 和 `y_max`。
4. 用 `fill_between` 画半透明包络。

相关属性：

- `background_alpha`：背景透明度，默认 `0.25`。
- `background_points`：背景插值采样点数，默认 `1000`。

如果背景组只有一条曲线，则画成半透明线。

## Properties

右侧 Properties 控制绘图设置。常用属性：

| 属性 | 说明 |
| --- | --- |
| `plot_type` | 轴标签组合，例如 `strain_stress_tempD` |
| `axis_labels` | 轴标签字典 |
| `right_axis_color` | 右轴颜色 |
| `loc` | legend 位置，例如 `best`、`upper right` |
| `plot_dpi` | 导出分辨率 |
| `fig_width_cm` | 绘图区内框目标宽度，单位 cm；宽高比作用在四方框以内 |
| `fig_height_cm` | 绘图区内框目标高度，单位 cm；例如 13:8 控制的是坐标轴四方框比例 |
| `legend_line_length` | legend 线段长度 |
| `label_decimal` | 右轴网格对齐时的舍入位数 |
| `marks` | marker 密度控制 |
| `background_alpha` | 背景包络透明度 |
| `background_points` | 背景包络插值点数 |
| `color_palette` | 自定义短颜色码 |
| `seperator` | CSV 分隔符 |
| `xmin` | x 轴下限，填 `None` 表示不限 |
| `xmax` | x 轴上限，填 `None` 表示不限 |
| `grid` | 是否显示网格，使用 `True` 或 `False` |

修改属性：

1. 在 Properties 中右键某一项。
2. 选择 `Edit Property`。
3. 输入新值。

插入属性：

1. 右键父节点，例如 `axis_labels` 或 `color_palette`。
2. 选择 `Insert Property`。
3. 输入属性名和值。

## plot_type 和轴标签

`plot_type` 用下划线组合轴标签键：

```text
x_y
x_y_right
```

例如：

```text
strain_stress
strain_stress_tempD
```

其中：

- 第一段是 x 轴标签 key。
- 第二段是左轴 y 标签 key。
- 第三段可选，是右轴 y 标签 key。

标签内容来自 `axis_labels`。

## 模板

模板只保存绘图设置，不保存曲线数据。

启动时 HyperPlot 会检查 `templates/` 目录里的默认模板，优先顺序：

```text
default.hpt.json
default.json
default.hptemplate
default
```

推荐只使用：

```text
templates/default.hpt.json
```

如果默认模板不存在，就使用程序内置默认设置。

导出模板：

1. 调整好 Properties。
2. 点击 Properties 旁边的 `Export Template`。
3. 模板会保存为：

```text
templates/YYYYMMDD_HHMMSS.hpt.json
```

加载模板：

- 将模板文件拖进 GUI。

模板内容示例：

```json
{
  "app": "HyperPlot",
  "kind": "template",
  "version": 1,
  "created_at": "2026-06-01T12:00:00",
  "preferences": {
    "plot_type": "strain_stress_tempD",
    "fig_width_cm": 9,
    "fig_height_cm": 9,
    "color_palette": {
      "r": "#e64b35",
      "g": "#00a087",
      "m": "#cc79a7"
    }
  }
}
```

## SVG 和 PNG 状态恢复

HyperPlot 导出的 SVG/PNG 会携带完整状态，包括：

- 曲线数据点 `x/y`
- legend
- line style
- 左右轴状态
- 背景组状态
- Properties 设置
- 自定义色板

拖拽这些文件回 GUI，就可以恢复曲线和设置。

注意：

- 普通外部 SVG/PNG 没有 HyperPlot 状态，拖入时会跳过。
- SVG 状态写在 `<metadata>` 里。
- PNG 状态写在 PNG text metadata 里。
- 如果只想把图发给别人看，SVG/PNG 仍然是普通图像文件。
- 如果想让别人也能恢复工程状态，需要保留由 HyperPlot 导出的原始 SVG/PNG。

## fastCSV

勾选 `fastCSV` 后，拖入 CSV 会快速读取并直接输出图像。

适合临时快速查看单个 CSV。普通工作流建议不勾选，先导入 Workbench，再选择曲线、设置样式并输出。

## Python 后端用法

最小示例：

```python
import HyperPlot

hp = HyperPlot.HyperPlot()
hp.catch("data.csv")
hp.out([0, 1], "Experiment==-ro|Simulation==--b", "result.svg")
```

读取多个 CSV：

```python
hp.catch(["a.csv", "b.csv"])
```

设置属性：

```python
hp.set_plot_preferences(
    plot_type="strain_stress_tempD",
    fig_width_cm=12,
    fig_height_cm=8,
    grid="True",
)
```

保存模板：

```python
hp.save_template()
```

加载模板：

```python
hp.load_template("templates/default.hpt.json")
```

恢复 SVG/PNG 状态：

```python
hp.catch_svg("plot.svg")
hp.catch_png("plot.png")
```

背景操作：

```python
hp.set_background([0, 1, 2])
hp.unset_background([0, 1])
hp.delete_elements([3])
hp.toggle_axis([0])
```

## 打包注意事项

这个项目依赖 `tkinterdnd2`、`tkinter`、`matplotlib`、`numpy`，读 CSV 时还会用到 `pandas`。

Nuitka 打包建议优先使用目录模式：

```bash
python -m nuitka --standalone --enable-plugin=tk-inter PlotCSV_GUI.py
```

如果使用 onefile，启动会慢一些，因为 `matplotlib`、`numpy`、`pandas` 等依赖体积较大，需要解包。

Linux 分发建议：

- 自用或同环境使用：`--standalone` 目录版。
- 发给别人桌面使用：考虑 AppImage。
- 为兼容老系统：在较老 Linux 环境中构建。

如果遇到 `GLIBCXX_xxx not found`，通常是构建机 GCC/libstdc++ 比目标机器新。

## 常见问题

### 拖入 SVG/PNG 没反应

只有 HyperPlot 导出的 SVG/PNG 才带可恢复状态。普通图像会被跳过。

### Batch Style 不生效

确认格式是：

```text
legend==style
```

多项用 `|` 分隔。背景组只占一个 Batch Style 项。

### color_palette 是空的

当前版本默认会显示完整色板。如果旧模板里保存了空色板 `{}`，加载该模板后可能覆盖默认色板。可以删除模板里的空 `color_palette`，或手动插入颜色项。

### PNG 能不能像 SVG 一样恢复？

可以。HyperPlot 导出的 PNG 会写入 metadata，拖回 GUI 可以恢复。外部 PNG 不行。

### 修改 Properties 后没有变化

点击 `Plot` 或 `Output` 后会重新生成图。部分属性需要重新绘图才会体现。

## 文件结构

```text
PlotCSV_GUI.py   GUI 前端
HyperPlot.py     兼容入口，保留旧的 import HyperPlot 用法
hyperplot/       后端包：模型、设置、模板、状态读写和绘图工程逻辑
templates/       模板目录
plots/           默认输出目录
tests/           后端回归测试
```

## 设计边界

当前结构把主要业务逻辑放在 `hyperplot/` 包里，`HyperPlot.py` 只做兼容转发：

- CSV/SVG/PNG/模板读取
- PlotElement 管理
- Batch Style 解析
- 背景包络绘制
- 图像导出和状态写入

GUI 主要负责：

- 拖拽文件
- 显示 Workbench
- 显示 Properties
- 调用后端 public 方法

开发时可以运行后端测试：

```bash
python3 -m unittest discover -s tests
```

如果继续做更严格的前后端分离，下一步可以把 Treeview 和 Listbox 所需的数据都通过更稳定的 public API 提供，避免 GUI 依赖后端内部字段。
