# 飞智 (Flydigi) 散热底座蓝牙协议逆向工程技术文档

本技术文档整理并归档了通过逆向分析飞智官方桌面客户端（Flydigi Space Station 3.0，基于 .NET Core / WPF 开发）所得的完整蓝牙通信与控制协议。

---

## 1. 官方程序集分析结构

官方客户端安装于 `C:\Program Files\FlydigiSpaceStation`，核心通信逻辑封装在以下组件中：
- `BLEServiceController.dll`：底座与外设的 BLE GATT 连接、服务发现、特征值订阅与指令收发。
- `Middleware.dll`：硬件协议层，包含 `Flydigi.BS` 命名空间下的所有数据封包结构体 (`*Proto`)、校验和计算、数据切片服务。
- `FlydigiSpaceStation.dll`：UI 控制与温控策略引擎。
- `config/bs/intelligent_thermalv4.json`：全系列散热支架（BS1、BS2、BS2 Pro、BS2 Pro IP）在 5V / 9V / 20V 供电下的完整温控风速曲线数据。

---

## 2. BLE 通信基础

- **蓝牙广播名称关键字**：`FlyDigi BS2` / `FlyDigi BS2PRO` / `BS2`
- **GATT 服务 (Service UUID)**：`0000fee7-0000-1000-8000-00805f9b34fb` (0xFFF0)
- **写入特征值 (Write Characteristic)**：`0000fea1-0000-1000-8000-00805f9b34fb` (0xFFF2)
- **通知特征值 (Notify Characteristic)**：`0000fea2-0000-1000-8000-00805f9b34fb` (0xFFF1)
- **写操作类型**：GATT Write Without Response（无应答直接写入）

---

## 3. 数据帧封包规范

所有发送与接收的数据帧均采用统一的格式头与尾部校验和：

```
+-----------+-----------+---------+--------+-------------------+----------+
|   0x5A    |   0xA5    | Command | Length |      Payload      | Checksum |
|  Header1  |  Header2  |  (1B)   |  (1B)  | (len = Length - 2)|   (1B)   |
+-----------+-----------+---------+--------+-------------------+----------+
```

### 3.1 字段定义
- `Header1`, `Header2`：固定为 `0x5A`, `0xA5`
- `Command`：单字节指令码（如 `0x21` 设置转速）
- `Length`：`len(Payload) + 2`（载荷字节数 + 2）
- `Payload`：实际参数载荷
- `Checksum`：低 8 位求和校验码：
  $$\text{Checksum} = (0x5A + 0xA5 + \text{Command} + \text{Length} + \sum \text{Payload}) \pmod{256}$$

---

## 4. 完整指令表速查

| 指令码 | 官方对应类名 | 功能描述 | 载荷格式 (Payload) | 回复/回调说明 |
|:---:|:---|:---|:---|:---|
| `0x01` | `GetFirmwareVersionProto` | 查询底座固件版本 | 空 | 回复版本字符串（如 `v0.0.3.5`） |
| `0x07` | `GetFastChargeModeProto` | 查询快充协议模式 | 空 | 回复单字节：`1`=5V, `2`=9V, `3`=20V PD |
| `0x08` | `SetFanSpeedMenualModeProto` | 切换手动固定档位 | `[gear]` (0~3 对应 1~4 档) | 无回复 |
| `0x0C` | `SetAutoStartProto` | 开机自启设置 | `[0/1]` | 无回复 |
| `0x0D` | `SetSmartStartStopProto` | 智能启停模式 | `[0/1/2]` (关/立即/延时) | 无回复 |
| `0x21` | `FanSpeedSettingProto` | 动态设置目标转速 | `[rpm_L, rpm_H]` (小端 16 位整数) | 无回复 |
| `0x22` | `FanSpeedConsultProto` | 查询当前实时转速 | 空 | 回复 `[cur_L, cur_H, tgt_L, tgt_H]` |
| `0x23` | `FanSpeedStartSmartProto` | 进入智能接管模式 | 空 | 底座指示灯转为呼吸状态 |
| `0x24` | `FanSpeedEndSmartProto` | **退出智能接管模式** | 空 | 底座释放接管，切回硬件按键控制 |
| `0x26` | `FanSpeedModeSettingProto` | 档位与基准转速绑定 | `[gear, rpm_L, rpm_H]` | 无回复 |
| `0x41` | `RGBPrepareProto` | RGB 配置表传输准备 | 空 | 开启分包接收缓冲区 |
| `0x43` | `RGBFinishProto` | RGB 配置表写入生效 | 空 | 校验并应用动画 |
| `0x44` | `RGBSetIntelligentModeProto`| RGB 智控联动模式 | `[mode]` | 无回复 |
| `0x46` | `RGBSetOnProto` | RGB 灯效总开关 | `[0/1]` | 无回复 |
| `0x47` | `RGBTransportOrderProto` | 传输 306B 动画切片 | `[order_index, ... 10 字节数据 ...]` | 连续发送 31 包 |
| `0x48` | `SetGearPositionLEDProto` | 档位数显 LED 开关 | `[0/1]` | 无回复 |

---

## 5. 306 字节 RGB 配置表逆向

官方 `RGBConfig` 结构体共包含 306 字节，内存排布如下：
- **Header (6 字节)**：
  - `0x00`：保留
  - `0x02`：协议版本
  - `LoopStart` (1B)：循环起始帧索引
  - `LoopEnd` (1B)：循环结束帧索引
  - `LoopTime` (1B)：帧渐变时间基准（数值越小越快，如 8/15/25）
  - `LightScale` (1B)：全局亮度百分比（0 ~ 100）
- **Color Blocks (300 字节)**：
  - 共 10 组，每组 10 个 RGB 颜色（每个颜色 3 字节：R, G, B）。
  - **单色呼吸模式实现机制**：设置 `LoopStart = 0`, `LoopEnd = 1`，其中第 0 帧颜色设为 `[0, 0, 0]`（暗灭），第 1 帧设为目标色 `[R, G, B]`。底座硬件将在这两帧之间进行正弦插值呼吸。
- **传输切片协议**：
  - 调用 `Bytes.SplitMsg(config_bytes, 10)` 切割为 31 块（每块最多 10 字节，不足 10 字节的末尾用 0 填充）。
  - 每块前插入单字节序号（`0x00` 到 `0x1E`），作为 `0x47` 指令的载荷依次发送。

---

## 6. 原厂温控曲线数据归档

官方原始温控曲线数据已完整备份于 [`docs/official_specs/intelligent_thermalv4.json`](intelligent_thermalv4.json)。

### BS2 Pro 20V 典型曲线关键采样点：
- **静音模式 (Silent)**：
  - 30°C ~ 40°C：1300 RPM
  - 50°C：1700 RPM
  - 60°C：2100 RPM
  - 70°C：2600 RPM
  - 80°C：3000 RPM
  - 90°C ~ 100°C：3400 RPM
- **性能模式 (Performance)**：
  - 30°C ~ 40°C：1700 RPM
  - 50°C：2400 RPM
  - 60°C：3000 RPM
  - 70°C：3500 RPM
  - 80°C ~ 100°C：4000 RPM (满载压制)
