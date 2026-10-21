# 飞智 BS2 / BS2 Pro 轻量化控制软件实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 基于逆向提取的协议，构建常驻内存 <30MB、永不退后台、开机自愈重连、包含深色仪表盘与系统托盘的飞智 BS2 / BS2 Pro 独立轻量控制软件。

**架构：** 解耦的四层架构：底层纯协议引擎（帧头与校验），BLE Worker 异步蓝牙重连守护层，温控曲线与传感器数据驱动层，以及基于 CustomTkinter + Pystray 的现代深色面板与系统托盘。

**技术栈：** Python 3.13, bleak, pythonnet, customtkinter, pystray, Pillow, pytest

**规格：** [docs/superpowers/specs/2026-10-21-bs2pro-controller-design.md](file:///d:/py/REA_Q-Dir/docs/superpowers/specs/2026-10-21-bs2pro-controller-design.md)

---

## 全局约束

- **运行平台**：Windows 10 / Windows 11 (64-bit)，依赖原生 Windows Bluetooth API (WinRT)。
- **编码与格式**：所有源码文件 UTF-8 编码，统一采用强类型注解 (`typing`)。
- **内存红线**：常驻内存严格控制在 35MB 以内。
- **协议精度**：报文前缀 `5A A5`，校验和必须为逐字节累加和低 8 位；转速为 16 位小端无符号整数。
- **容错设计**：所有硬件通信调用与外部异常均不得导致 UI 进程闪退，蓝牙断开自动静默退避重连。

## 审查重点（Review Focus）

1. **输入异常与校验和溢出**：若传入负数转速或超过 4000 的转速，协议引擎必须钳位在有效范围 [0, 4000]，避免发送畸形小端字节打崩单片机。
2. **报文长度与分包粘包**：BLE Notify 回包长度不满足 7 字节时，解包器需安全丢弃而不是抛出 `IndexError`。
3. **传感器读取失败或单硬件缺失**：核显笔记本无独立 GPU 或在省电休眠时，传感器模块不得抛出异常，自动以 CPU 单温作为有效温控基准。
4. **急速升降温抖动 (Fan Throttling Hunt)**：临界温度（如 59.9°C $\leftrightarrow$ 60.1°C）跳变时，滞后防抖算法必须锁定下探区间至少 2°C，防止风扇高频升降速哮叫。
5. **蓝牙断开/设备关闭时退出进程**：当主程序退出或托盘点击“退出”时，必须主动优雅发送 `0x24` 释放智能托管并断开 BLE 连接，避免设备单片机处于挂起状态。

---

## 文件结构规划

```
flydigi_bs2_controller/
├── core/
│   ├── __init__.py
│   ├── protocol.py          # 帧打包、解包、校验和、各功能指令生成器
│   ├── config.py            # JSON 配置读写 (AppConfig 数据类)
│   ├── curve_engine.py      # 温控曲线预设、自定义插值与降温滞后滤波
│   ├── sensor.py            # CPU / GPU 硬件温度采集抽象与 fallback 驱动
│   └── ble_worker.py        # Bleak 异步非阻塞蓝牙守护、发现与状态轮询
├── ui/
│   ├── __init__.py
│   ├── widgets.py           # CustomTkinter 自定义半圆仪表盘与曲线拖拽组件
│   ├── app.py               # 控制面板主窗口 (深色主题、布局、事件绑定)
│   └── tray.py              # Pystray 系统托盘常驻图标、悬停气泡与右键菜单
├── main.py                  # 应用程序主入口 (进程单例、事件总线串联)
├── config.json              # 默认/用户持久化配置文件
└── requirements.txt         # 生产依赖说明
tests/
├── test_protocol.py         # 协议编解码与边界测试
├── test_config.py           # 配置读写与异常恢复测试
├── test_curve_engine.py     # 曲线插值、功率钳位与防抖滤波测试
├── test_sensor.py           # 传感器探测与模拟容灾测试
└── test_ble_worker.py       # 蓝牙守护与重连状态机模拟测试
```

---

### 任务 1：协议引擎与编解码驱动 (BS2Protocol)

**文件：**
- 创建：`flydigi_bs2_controller/core/__init__.py`
- 创建：`flydigi_bs2_controller/core/protocol.py`
- 测试：`tests/test_protocol.py`

- [ ] **步骤 1：编写失败的协议单元测试**

```python
# tests/test_protocol.py
import pytest
from flydigi_bs2_controller.core.protocol import BS2Protocol

def test_calc_checksum():
    # 0x01 + 0x03 = 0x04
    assert BS2Protocol.calc_checksum(0x01, 0x03, b"") == 0x04
    # 0x21 + 0x05 + 0xDC + 0x05 = 0x107 -> 0x07
    assert BS2Protocol.calc_checksum(0x21, 0x05, bytes([0xDC, 0x05])) == 0x07

def test_pack_unpack_command():
    pkt = BS2Protocol.pack(0x21, bytes([0xDC, 0x05]))
    assert pkt == bytes([0x5A, 0xA5, 0x21, 0x05, 0xDC, 0x05, 0x07])
    cmd, payload = BS2Protocol.unpack(pkt)
    assert cmd == 0x21
    assert payload == bytes([0xDC, 0x05])

def test_fan_speed_command():
    pkt = BS2Protocol.build_set_rpm(1500)
    assert pkt == bytes([0x5A, 0xA5, 0x21, 0x05, 0xDC, 0x05, 0x07])

def test_gear_led_and_auto_start():
    assert BS2Protocol.build_set_gear_led(True) == bytes([0x5A, 0xA5, 0x48, 0x04, 0x01, 0x4D])
    assert BS2Protocol.build_set_auto_start(True) == bytes([0x5A, 0xA5, 0x0C, 0x04, 0x01, 0x11])
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_protocol.py -v`  
预期：FAIL，`ModuleNotFoundError: No module named 'flydigi_bs2_controller'`

- [ ] **步骤 3：实现 `BS2Protocol` 核心封装类**

在 `flydigi_bs2_controller/core/protocol.py` 中实现：
- `HEADER = b"\x5A\xA5"`
- 各命令常量：`CMD_FIRMWARE = 0x01`, `CMD_FAST_CHARGE = 0x07`, `CMD_AUTO_START = 0x0C`, `CMD_SMART_START_STOP = 0x0D`, `CMD_SET_RPM = 0x21`, `CMD_CONSULT_RPM = 0x22`, `CMD_START_SMART = 0x23`, `CMD_END_SMART = 0x24`, `CMD_SET_RGB_INTELLIGENT = 0x44`, `CMD_SET_RGB_STATE = 0x46`, `CMD_SET_GEAR_LED = 0x48`
- `calc_checksum(cmd_id: int, length: int, payload: bytes) -> int`
- `pack(cmd_id: int, payload: bytes = b"") -> bytes`
- `unpack(raw: bytes) -> tuple[int, bytes]`
- `build_set_rpm(rpm: int) -> bytes`（内部限制 `0 <= rpm <= 4000` 并转小端 2 字节）
- `parse_consult_rpm(payload: bytes) -> tuple[int, int]`（返回当前转速和目标转速）
- 各控制函数：`build_set_gear_led`, `build_set_auto_start`, `build_set_smart_start_stop`, `build_set_rgb_state`, `build_set_rgb_intelligent`, `build_query_fast_charge`

- [ ] **步骤 4：运行测试验证全部通过**

运行：`pytest tests/test_protocol.py -v`  
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add flydigi_bs2_controller/core/__init__.py flydigi_bs2_controller/core/protocol.py tests/test_protocol.py
git commit -m "feat(protocol): implement BS2 protocol packet framing and commands"
```

---

### 任务 2：配置持久化管理模块 (ConfigManager)

**文件：**
- 创建：`flydigi_bs2_controller/core/config.py`
- 测试：`tests/test_config.py`

- [ ] **步骤 1：编写失败的配置管理测试**

```python
# tests/test_config.py
import os
from flydigi_bs2_controller.core.config import ConfigManager, AppConfig

def test_default_config():
    cfg = AppConfig()
    assert cfg.cooling_mode == "smart"
    assert cfg.smart_preset == "silent"
    assert cfg.gear_led is True
    assert cfg.auto_start is True
    assert len(cfg.custom_curve) == 8

def test_save_and_load(tmp_path):
    config_file = str(tmp_path / "test_config.json")
    mgr = ConfigManager(config_file)
    mgr.config.cooling_mode = "fixed"
    mgr.config.fixed_rpm = 2500
    mgr.save()

    new_mgr = ConfigManager(config_file)
    assert new_mgr.config.cooling_mode == "fixed"
    assert new_mgr.config.fixed_rpm == 2500
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_config.py -v`  
预期：FAIL，找不到 `ConfigManager`

- [ ] **步骤 3：实现 `ConfigManager` 与 `AppConfig`**

在 `flydigi_bs2_controller/core/config.py` 中：
- 使用 `@dataclass` 定义 `AppConfig`：
  - `cooling_mode: str = "smart"` ("smart" | "fixed")
  - `smart_preset: str = "silent"` ("silent" | "performance" | "custom")
  - `fixed_rpm: int = 2000`
  - `gear_led: bool = True`
  - `auto_start: bool = True`
  - `smart_start_stop: int = 1` (0: 关, 1: 即时, 2: 延时)
  - `rgb_mode: int = 6` (6: 智能模式)
  - `custom_curve: list[list[int]]`（默认 30°C:1300 到 100°C:4000）
- 实现 `ConfigManager`，支持 `load()`, `save()`，当文件损坏时自动回退默认并备份。

- [ ] **步骤 4：运行测试验证通过**

运行：`pytest tests/test_config.py -v`  
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add flydigi_bs2_controller/core/config.py tests/test_config.py
git commit -m "feat(config): implement AppConfig and JSON persistence"
```

---

### 任务 3：温控曲线计算与插值引擎 (CurveEngine)

**文件：**
- 创建：`flydigi_bs2_controller/core/curve_engine.py`
- 测试：`tests/test_curve_engine.py`

- [ ] **步骤 1：编写失败的曲线引擎测试**

```python
# tests/test_curve_engine.py
from flydigi_bs2_controller.core.curve_engine import CurveEngine

def test_preset_silent_curve():
    engine = CurveEngine()
    engine.set_power_mode(3) # 20V, max 4000
    engine.set_mode("silent")
    # 30度时最低 1300
    assert engine.calculate_target_rpm(25.0) == 1300
    assert engine.calculate_target_rpm(30.0) == 1300
    # 80度以上拉高
    assert engine.calculate_target_rpm(85.0) >= 3000

def test_power_mode_clamping():
    engine = CurveEngine()
    engine.set_power_mode(1) # 5V, max 2700
    engine.set_mode("performance")
    assert engine.calculate_target_rpm(100.0) == 2700

def test_hysteresis_smoothing():
    engine = CurveEngine(hysteresis=2.0)
    engine.set_mode("performance")
    rpm1 = engine.calculate_smooth_rpm(70.0)
    # 温度微降 1 度 (在 2 度死区内)，转速不应骤降
    rpm2 = engine.calculate_smooth_rpm(69.0)
    assert rpm2 == rpm1
    # 温度升至 75 度，应立即响应上升
    rpm3 = engine.calculate_smooth_rpm(75.0)
    assert rpm3 > rpm1
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_curve_engine.py -v`  
预期：FAIL，找不到 `CurveEngine`

- [ ] **步骤 3：实现 `CurveEngine` 类**

在 `flydigi_bs2_controller/core/curve_engine.py` 中实现：
- 预设曲线常量（复刻官方 `intelligent_thermalv4.json` 中 BS2Pro 数据）。
- `set_power_mode(mode: int)`：根据回包设置最大 RPM（5V: 2700, 9V: 3300, 20V: 4000）。
- `linear_interpolate(temp: float, points: list[list[int]]) -> int`：分段线性插值。
- `calculate_smooth_rpm(temp: float) -> int`：结合 2°C 降温滞后滤波与 100 RPM 整百对齐。

- [ ] **步骤 4：运行测试验证通过**

运行：`pytest tests/test_curve_engine.py -v`  
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add flydigi_bs2_controller/core/curve_engine.py tests/test_curve_engine.py
git commit -m "feat(curve): implement curve interpolation and hysteresis engine"
```

---

### 任务 4：硬件温度传感器采集驱动 (HardwareSensor)

**文件：**
- 创建：`flydigi_bs2_controller/core/sensor.py`
- 测试：`tests/test_sensor.py`

- [ ] **步骤 1：编写失败的传感器采集测试**

```python
# tests/test_sensor.py
from flydigi_bs2_controller.core.sensor import HardwareSensor

def test_sensor_fallback_and_range():
    sensor = HardwareSensor()
    cpu_temp, gpu_temp = sensor.get_temperatures()
    assert isinstance(cpu_temp, (int, float))
    assert isinstance(gpu_temp, (int, float))
    eff_temp = sensor.get_effective_temp()
    assert 10.0 <= eff_temp <= 115.0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_sensor.py -v`  
预期：FAIL，找不到 `HardwareSensor`

- [ ] **步骤 3：实现 `HardwareSensor`**

在 `flydigi_bs2_controller/core/sensor.py` 中实现：
- 优先尝试通过 `pythonnet` 加载 `C:\Program Files\FlydigiSpaceStation\LibreHardwareMonitorLib.dll` 采集 CPU (`Core (Tctl/Tdie)` / `CPU Package`) 和 GPU (`GPU Core`)。
- 若无法加载驱动或缺少 admin 权限，优雅回退至 NVAPI / WMI / 模拟平滑温控测试源。
- `get_effective_temp() -> float` 返回 $\max(T_{\text{CPU}}, T_{\text{GPU}})$。

- [ ] **步骤 4：运行测试验证通过**

运行：`pytest tests/test_sensor.py -v`  
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add flydigi_bs2_controller/core/sensor.py tests/test_sensor.py
git commit -m "feat(sensor): implement LibreHardwareMonitor integration and fallback"
```

---

### 任务 5：异步蓝牙守护与重连状态机 (BLEWorker)

**文件：**
- 创建：`flydigi_bs2_controller/core/ble_worker.py`
- 测试：`tests/test_ble_worker.py`

- [ ] **步骤 1：编写失败的 BLEWorker 模拟测试**

```python
# tests/test_ble_worker.py
import pytest
from flydigi_bs2_controller.core.ble_worker import BLEWorker, ConnectionState

def test_worker_initial_state():
    worker = BLEWorker()
    assert worker.state == ConnectionState.DISCONNECTED
    assert worker.current_rpm == 0
    assert worker.target_rpm == 0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_ble_worker.py -v`  
预期：FAIL，找不到 `BLEWorker`

- [ ] **步骤 3：实现 `BLEWorker`**

在 `flydigi_bs2_controller/core/ble_worker.py` 中实现：
- `ConnectionState` 枚举：`DISCONNECTED`, `SCANNING`, `CONNECTED`, `SYNCED`
- 使用独立子线程跑 `asyncio` 事件循环，避免阻塞 Tkinter UI。
- `BleakScanner` 过滤名称包含 `"Flydigi BS2"` 或 `"Flydigi BS1"` 的蓝牙外设。
- 连接成功后开启 `Notify (0xFFF1)` 监听，并在回调中解包实际转速与供电电压。
- 1 秒主循环：发送最新目标转速，轮询当前转速。
- 异常断开自动触发重连，间隔 3 秒退避，自愈连接。

- [ ] **步骤 4：运行测试验证通过**

运行：`pytest tests/test_ble_worker.py -v`  
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add flydigi_bs2_controller/core/ble_worker.py tests/test_ble_worker.py
git commit -m "feat(ble): implement asynchronous BLE worker with auto-reconnect"
```

---

### 任务 6：现代深色仪表盘主界面 (CustomTkinter GUI)

**文件：**
- 创建：`flydigi_bs2_controller/ui/__init__.py`
- 创建：`flydigi_bs2_controller/ui/widgets.py`
- 创建：`flydigi_bs2_controller/ui/app.py`

- [ ] **步骤 1：实现自定义仪表盘与曲线组件 (`widgets.py`)**

在 `flydigi_bs2_controller/ui/widgets.py` 中：
- `CircularGauge`：基于 `tk.Canvas` 实现半圆弧仪表盘，渲染渐变圆环、指针旋转、中心超大字号实时温度（如 `41°C`）与转速（如 `1300rpm`）。
- `CurveCanvas`：绘制 30°C ~ 100°C 8 个节点的折线与平滑曲线，在“自定义模式”下支持鼠标左键拖动节点修改转速，实时更新曲线数据。

- [ ] **步骤 2：实现控制面板主窗口 (`app.py`)**

在 `flydigi_bs2_controller/ui/app.py` 中：
- 采用 `customtkinter` 深色主题（Dark theme，背景色 `#121212`，强调色 `#00A8FF` 与 `#FF5722`）。
- **左侧**：放置 `CircularGauge` 仪表盘，显示设备温度与实时转速。
- **右侧**：
  - 最大超频转速指示（动态变色：20V 显示绿色 `4000rpm`）。
  - 散热模式分段按钮：`智能变频` vs `固定转速`。
  - 智能变频下拉菜单：`静音模式`、`性能模式`、`自定义模式`。
  - `CurveCanvas` 曲线图表面板。
  - 开关组：`档位灯显示`（Switch）、`通电自启功能`（Switch）。
  - 下拉选框：`灯光模式`（智能/常亮/呼吸/关闭）、`智能启停`（即时运行/延时/关闭）。
- 窗口右上角 `X` 拦截：调用 `self.withdraw()` 隐藏至系统托盘，而非直接终止进程。

- [ ] **步骤 3：编写 GUI 实例化与组件健全性测试**

```python
# tests/test_gui.py
import pytest
from flydigi_bs2_controller.core.config import AppConfig
from flydigi_bs2_controller.ui.app import MainWindow

def test_gui_create():
    # 测试 GUI 可以正常初始化无崩溃
    app = MainWindow(AppConfig(), None)
    assert app is not None
    app.destroy()
```

- [ ] **步骤 4：运行测试确认界面无报错**

运行：`pytest tests/test_gui.py -v`  
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add flydigi_bs2_controller/ui/__init__.py flydigi_bs2_controller/ui/widgets.py flydigi_bs2_controller/ui/app.py tests/test_gui.py
git commit -m "feat(ui): implement modern dark theme dashboard and curve editor"
```

---

### 任务 7：系统托盘与主程序总成 (Pystray & Main Entry)

**文件：**
- 创建：`flydigi_bs2_controller/ui/tray.py`
- 创建：`flydigi_bs2_controller/main.py`
- 创建：`flydigi_bs2_controller/requirements.txt`

- [ ] **步骤 1：实现托盘组件 (`tray.py`)**

在 `flydigi_bs2_controller/ui/tray.py` 中：
- 使用 `Pillow` 动态生成或加载飞智 Logo 托盘小图标。
- 绑定右键菜单：
  - `显示控制面板`（点击还原并置顶主窗口）
  - `模式切换`（静音 / 性能 / 智能 / 固定）
  - `档位灯开关`
  - `开机自启`
  - `退出软件`（优雅断开 BLE 并退出整个进程）
- 动态更新托盘 Tooltip 悬浮提示：`飞智 BS2 Pro [已连接] | CPU: 42°C | 1450 RPM`。

- [ ] **步骤 2：实现主程序入口 (`main.py`)**

在 `flydigi_bs2_controller/main.py` 中：
- 使用 `pywin32` 互斥体（Mutex）确保单实例运行，避免多开冲突。
- 实例化 `ConfigManager`, `CurveEngine`, `HardwareSensor`, `BLEWorker`, `MainWindow`, `TrayIcon`。
- 设置 1 秒定时器同步数据：传感器采样 $\to$ 曲线引擎计算目标 RPM $\to$ 注入 BLEWorker $\to$ 更新 UI 仪表盘与托盘气泡。

- [ ] **步骤 3：编写启动与全套集成自动化验证**

运行完整测试套件：`pytest tests/ -v`  
预期：所有测试 100% 通过。

- [ ] **步骤 4：实际启动运行并验证硬件连通性与内存占用**

运行：`python flydigi_bs2_controller/main.py`  
检查任务管理器中内存占用是否稳定在 20MB~30MB 之间。

- [ ] **步骤 5：Commit**

```bash
git add flydigi_bs2_controller/ui/tray.py flydigi_bs2_controller/main.py flydigi_bs2_controller/requirements.txt
git commit -m "feat: complete flydigi bs2 pro lightweight controller integration"
```
