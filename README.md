# 飞智 BS2 / BS2 Pro 笔记本散热支架极简开源控制器 (Flydigi BS2 Pro Controller)

<p align="center">
  <b>极简 · 超轻量 · 零捆绑 · 原生蓝牙控制 · 硬件状态完全还原</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/RAM-%3C%2030MB-brightgreen" alt="RAM < 30MB">
  <img src="https://img.shields.io/badge/License-MIT-orange" alt="MIT License">
</p>

---

## 📖 项目简介 (Introduction)

本项目是针对**飞智 (Flydigi) BS2 / BS2 Pro 笔记本压风式散热支架**逆向工程开发的第三方极简独立控制程序。

官方“飞智空间站 3.0 (Flydigi Space Station)”体积庞大（数以百兆的 Electron / .NET 运行时），后台内存占用动辄 **300MB ~ 500MB+**，且偶尔伴随自启失灵、进程残留或风扇控制断开等问题。

**Flydigi BS2 Pro Controller** 采用轻量化 Python + Windows 原生 WinRT BLE 编写，具备以下优势：
- 🚀 **极度轻量**：单文件打包 `.exe` 仅约 20MB，常驻内存仅 **~25MB - 30MB**，CPU 占用几乎为 **0%**。
- 🧊 **完整温控曲线引擎**：实时采集 CPU / GPU 综合温度，具备 5 秒迟滞平滑 (Hysteresis) 算法，防止转速忽高忽低产生烦人风噪。
- ⚡ **对标原厂智能预设**：深度逆向官方 `intelligent_thermalv4.json`，完整支持 20V/9V/5V 供电自适应下的 **静音 (Silent)**、**性能 (Performance)** 与 **自定义多段曲线**。
- 🎛️ **固定转速模式**：支持 4 档快捷切换（1档 1700 / 2档 2400 / 3档 3000 / 4档 4000 RPM）及 1300 ~ 4000 RPM 无级滑块精准锁速。
- 🌈 **306 字节全功能 RGB 引擎**：完整逆向官方分包传输协议（`0x41` -> 31包 `0x47` -> `0x43`），支持流光、旋转、单色、多色、**真实呼吸 (Breathing)** 及智控联动。
- 🛡️ **优雅退出与硬件防呆**：无论是关闭窗口、托盘退出、命令行 `Ctrl+C` 还是 Windows 关机，程序均通过 Windows Console Control 机制向硬件发送 `0x24` 释放指令，保证退出后散热底座立即恢复原厂待机/按键状态，绝不卡死在全速。
- 🔔 **开机自启动与托盘静默**：提供 PowerShell 一键安装开机自启快捷方式，开机自动静默潜伏至右下角系统托盘。

---

## 🛠️ 逆向工程协议解析 (Reverse-Engineered BLE Protocol)

通过对官方 `BLEServiceController.dll`、`Middleware.dll` 及 `FlydigiSpaceStation.dll` 的深入分析，提取出底座完整 GATT 通信协议：

### 1. BLE 服务与特征值 (GATT UUIDs)
- **Service UUID**: `0000fee7-0000-1000-8000-00805f9b34fb`
- **Write UUID**: `0000fea1-0000-1000-8000-00805f9b34fb` (写入指令)
- **Notify UUID**: `0000fea2-0000-1000-8000-00805f9b34fb` (遥测与状态回调)

### 2. 数据帧格式 (Packet Structure)
每个指令帧格式如下：
```
+---------+---------+---------+---------+------------------+----------+
|  0x5A   |  0xA5   | Command | Length  |     Payload      | Checksum |
| Header1 | Header2 | (1B)    | (1B)    | (len = Length-2) |   (1B)   |
+---------+---------+---------+---------+------------------+----------+
```
> **校验和规则**：`Checksum = (Header1 + Header2 + Command + Length + sum(Payload)) & 0xFF`

### 3. 核心指令表 (Command Set)
| 指令码 | 官方协议类名 | 说明与载荷格式 |
|:---:|:---|:---|
| `0x01` | `GetFirmwareVersionProto` | 查询固件版本（如 `v0.0.3.5`） |
| `0x07` | `GetFastChargeModeProto` | 查询供电协议（`1`: 5V, `2`: 9V, `3`: 20V 快充） |
| `0x08` | `SetFanSpeedMenualModeProto` | 切换手动档位（`0..3` 对应 1~4 档） |
| `0x0C` | `SetAutoStartProto` | 自动启停开关 (`0`/`1`) |
| `0x0D` | `SetSmartStartStopProto` | 智能启停模式 (`0`: 关, `1`: 立即, `2`: 延时) |
| `0x21` | `FanSpeedSettingProto` | 设置目标转速（`Payload: [rpm_L, rpm_H]`） |
| `0x22` | `FanSpeedConsultProto` | 查询实时遥测（底座回复：`[cur_L, cur_H, tgt_L, tgt_H]`） |
| `0x23` | `FanSpeedStartSmartProto` | 开启智能调速接管模式（呼吸指示灯常亮） |
| `0x24` | `FanSpeedEndSmartProto` | **退出智能模式接管**（释放底座回退至硬件按键模式） |
| `0x26` | `FanSpeedModeSettingProto` | 档位与基准转速绑定 (`[gear, speed_L, speed_H]`) |
| `0x41` | `RGBPrepareProto` | RGB 配置表传输握手准备 |
| `0x43` | `RGBFinishProto` | RGB 配置表写入完成生效 |
| `0x44` | `RGBSetIntelligentModeProto` | 设置 RGB 智能联动模式 |
| `0x46` | `RGBSetOnProto` | RGB 总开关 (`0`: 关, `1`: 开) |
| `0x47` | `RGBTransportOrderProto` | 传输 306 字节 RGB 动画配置切片（共 31 包，每包 10 字节数据） |
| `0x48` | `SetGearPositionLEDProto` | 档位与转速数显指示灯开关 (`0`/`1`) |

### 4. 306 字节 RGB 配置结构
官方将灯效映射为 306 字节内存块：
- 前 6 字节为头信息：`[0x00, 0x02, LoopStart, LoopEnd, LoopTime, LightScale]`
- 后续跟 10 组颜色定义（每组包含 10 个 RGB 关键帧，共 300 字节）。
- 以**呼吸灯**为例：`LoopStart=0`, `LoopEnd=1`, Color[0]=`[0,0,0]`, Color[1]=`[R,G,B]`，底座硬件固件将自动在暗灭与目标颜色之间进行渐变呼吸过渡。

---

## 🚀 快速使用 (Getting Started)

### 方案 A：直接运行打包好的单文件程序（推荐）
1. 从 Releases 或本项目 [`dist/FlydigiBS2Controller.exe`](file:///D:/py/REA_Q-Dir/dist/FlydigiBS2Controller.exe) 下载可执行文件。
2. 确保电脑已在 Windows 蓝牙设置中与 `FlyDigi BS2` 或 `FlyDigi BS2PRO` 配对。
3. 双击 `FlydigiBS2Controller.exe` 即可使用！

### 方案 B：从源码运行
```powershell
# 1. 克隆仓库
git clone https://github.com/zhugeshu/Flydigi-BS2-Pro-Controller.git
cd Flydigi-BS2-Pro-Controller

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行程序
python run_controller.py
```

---

## ⚙️ 开机自启动设置 (Auto-start on Boot)

项目内提供配置脚本 [`scripts/manage_autostart.ps1`](file:///D:/py/REA_Q-Dir/scripts/manage_autostart.ps1)：

```powershell
# 开启开机自启动（开机后静默潜伏至右下角系统托盘，不弹窗）
powershell -File scripts/manage_autostart.ps1

# 查看当前自启动状态
powershell -File scripts/manage_autostart.ps1 -Status

# 取消开机自启动
powershell -File scripts/manage_autostart.ps1 -Disable
```

---

## 📦 自行打包 (Build Standalone EXE)

如需自行修改源码后打包单文件 `.exe`：
```powershell
python -m PyInstaller --noconsole --onefile --name "FlydigiBS2Controller" --paths . --collect-all customtkinter --collect-all winrt --hidden-import flydigi_bs2_controller --hidden-import flydigi_bs2_controller.core --hidden-import flydigi_bs2_controller.ui --clean run_controller.py
```
生成的可执行文件将位于 `dist/FlydigiBS2Controller.exe`。

---

## 🧪 自动化测试 (Testing)
项目包含覆盖协议封包拆包、曲线插值与迟滞计算、传感器回退、BLE 指令流以及 GUI 回调的完整自动化测试用例：
```powershell
pytest
```
```
============================= 31 passed in 2.23s ==============================
```

---

## 📄 开源许可证 (License)
本项目基于 [MIT License](file:///D:/py/REA_Q-Dir/LICENSE) 开源。

*免责声明：本软件为开源业余技术研究与逆向工程成果，与飞智科技 (Flydigi) 官方无关。“飞智”与“Flydigi”商标权利归其合法所有者所有。*
