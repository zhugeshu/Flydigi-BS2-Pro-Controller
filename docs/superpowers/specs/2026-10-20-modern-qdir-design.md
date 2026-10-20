# 现代版 Q-Dir (Modern Q-Dir) 系统设计规格说明书

- **日期**：2026-10-20
- **版本**：1.0.0
- **目标**：以现代 WinUI 3 (Windows App SDK) 与 .NET 8 技术栈重现经典 Q-Dir 的核心灵魂——保留 1~4 窗格高密度平铺、快捷文件操作与跨窗格交互能力，同时融入 Windows 11 Fluent Design（Mica 云母、圆角、现代深浅色主题）。

---

## 1. 背景与核心价值

经典 Q-Dir 凭借不到 2MB 的极简体积和独创的 4 窗格（Quad-Pane）平铺布局，在高级用户群体中拥有不可替代的地位。然而其基于 2005 时代 Win32 GDI/ComCtl 的外观与现代 Windows 11 视觉严重割裂。
现有现代开源文件管理器（如 Files）虽然外观美观，但主要面向轻量日常浏览，最多仅支持左右双窗格，缺乏 Q-Dir 标志性的田字格多窗格与极高信息密度。

本项目旨在填补这一空白：**打造一款原生 Fluent 现代视觉的高密度 4 窗格文件工作台**。

---

## 2. 技术选型与运行环境

- **运行环境**：Windows 10 1809 (Build 17763) 及以上，完美适配 Windows 11
- **开发框架**：C# 12 / .NET 8 (`net8.0-windows10.0.19041.0`)
- **UI 引擎**：WinUI 3 (Windows App SDK 1.5+)
- **架构模式**：MVVM 模式，采用 `CommunityToolkit.Mvvm` 进行解耦与属性通知
- **部署形式**：免打包单机绿色版（Unpackaged Portable），无需 MSIX 容器即可直接解压运行

---

## 3. 系统分层架构

系统划分为 UI 层、ViewModel 状态层、底层系统服务层三大模块：

```
+---------------------------------------------------------------+
|                       MainWindow (WinUI 3)                    |
|  - 自定义沉浸式 Mica 标题栏 (AppTitleBar)                      |
|  - 顶部全局工具栏 (布局切换: 1/2H/2V/3/4 窗格, 快速配置)      |
|  - QuadGridHost (2x2 网格容器 + 交叉 GridSplitter 分割线)      |
+---------------------------------------------------------------+
       |                       |                       |
       v                       v                       v
[FolderPaneView 1]     [FolderPaneView 2]      [FolderPaneView 3/4]
  - 路径导航条 (Breadcrumb + Editable TextBox)
  - 紧凑型文件列表 (Compact ListView, 24px 行高)
  - 状态栏 (项目总数、已选大小)
       |
       v (数据绑定 DataBinding)
[FolderPaneViewModel] (独立维护目录状态、选中项、前进/后退栈)
       |
       +---> [FileSystemProvider] (异步目录遍历、文件变更监听)
       +---> [ShellThumbnailService] (系统高清文件小图标提取)
       +---> [ShellOperationService] (原生复制/移动/删除/拖拽支持)
```

---

## 4. 核心功能与模块规范

### 4.1 四窗格布局引擎（QuadGridManager）
- **网格构成**：由一个 `Grid` 构成，包含两行两列（`RowDefinitions`: `*, *`，`ColumnDefinitions`: `*, *`）。
- **分割条交互**：
  - 1 根水平 `GridSplitter`，1 根垂直 `GridSplitter`。
  - 用户可自由拖曳分割条调整上下、左右面积比例。
- **5 种标准布局预设**：
  1. **单窗格 (1-Pane)**：Pane 1 占满全部 $(RowSpan=2, ColSpan=2)$，其余隐藏。
  2. **垂直双窗格 (2-Pane-V)**：Pane 1 居左 $(Col=0, RowSpan=2)$，Pane 2 居右 $(Col=1, RowSpan=2)$。
  3. **水平双窗格 (2-Pane-H)**：Pane 1 居上 $(Row=0, ColSpan=2)$，Pane 2 居下 $(Row=1, ColSpan=2)$。
  4. **三窗格 (3-Pane)**：左侧 Pane 1 $(RowSpan=2)$，右侧上下平铺 Pane 2 与 Pane 3。
  5. **四窗格 (4-Pane Quad)**：左上(NW)、右上(NE)、左下(SW)、右下(SE) 四象限全开。

### 4.2 紧凑型 Fluent 视图规范（Compact ListView）
- **紧凑样式覆盖**：
  - 重写 WinUI 3 `ListViewItemPresenter` 默认样式。
  - 单行高度设定为 **24px ~ 26px**，间距设为 0。
  - 图标采用 16x16 紧凑尺寸，正文字号 12.5px。
- **标准详情列**：
  1. 名称（含文件类型专属图标）
  2. 修改日期（`yyyy-MM-dd HH:mm`）
  3. 类型（如：文件夹、文本文件、可执行文件）
  4. 大小（智能格式化：B / KB / MB / GB，文件夹留空或统计项目数）
- **高对比活动状态标识**：
  - 当前处于输入焦点和活动状态的窗格（Active Pane），其外边框具有平滑淡入的 Win11 主题强调色（Accent Color），确保用户清晰感知操作目标。

### 4.3 核心交互与文件系统流
- **异步非阻塞加载**：所有目录读取使用 `IAsyncEnumerable` 或异步分批刷新，确保数万个文件的目录秒开、UI 线程始终 60fps 响应。
- **键盘导航映射**：
  - `Tab` / 鼠标单机：循环切换活动窗格。
  - `Enter` / 鼠标双击：进入选中文件夹，或调用默认关联程序打开文件。
  - `Backspace` / `Alt + Up`：返回上一级目录。
  - `Delete`：删除选中文件到回收站。
  - `Ctrl + C / X / V`：剪贴板文件复制、剪切、粘贴。
- **跨窗格拖拽支持（Drag and Drop）**：
  - 允许在窗格之间直接拖拽文件（`DragStarting` / `Drop`）。
  - 默认动作：跨盘符拖拽为“复制”，同盘符拖拽为“移动”，支持 `Ctrl` 键强制复制。

---

## 5. 项目工程结构规划

```
ModernQDir/
├── ModernQDir.sln
├── src/
│   ├── ModernQDir/
│   │   ├── ModernQDir.csproj          # .NET 8 WinUI 3 Unpackaged 工程
│   │   ├── App.xaml / App.xaml.cs     # 应用生命周期、全局资源与主题
│   │   ├── MainWindow.xaml / .cs      # 主窗口、Mica 材质挂载、标题栏与 QuadGrid
│   │   ├── Views/
│   │   │   ├── FolderPaneView.xaml    # 单个文件窗格用户控件
│   │   │   └── Controls/
│   │   │       └── BreadcrumbBar.xaml # 路径导航与编辑控件
│   │   ├── ViewModels/
│   │   │   ├── MainViewModel.cs       # 布局状态、全局设置管理
│   │   │   ├── FolderPaneViewModel.cs # 单窗格状态机（路径、文件列表、历史）
│   │   │   └── FileItemViewModel.cs   # 单个文件项（图标、名称、大小等）
│   │   ├── Services/
│   │   │   ├── FileSystemProvider.cs  # 磁盘 I/O、排序、过滤
│   │   │   └── ShellService.cs        # Win32 Shell API（图标提取、关联启动）
│   │   └── Styles/
│   │       └── CompactStyles.xaml     # 紧凑型 ListView 与 Fluent Token 定制
```

---

## 6. 成功验证标准

1. **环境准备与编译运行**：可在无打包依赖环境下通过 `dotnet run` 成功启动。
2. **布局无缝切换**：工具栏点击 1/2/3/4 窗格按钮可瞬间完成平铺重排，分割条可自由拖拽缩放。
3. **高密度视觉呈现**：单屏可容纳的文件数量显著多于系统自带 Explorer，整体呈现 Win11 Mica 现代圆角视觉。
4. **完整文件操作链**：支持在 4 个窗格中分别浏览不同目录，并能顺畅进行跨窗格拖拽、双击打开和快捷键导航。
