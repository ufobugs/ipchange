# 公网 IP 变更监控

这是一个轻量级 Python 脚本，用于定时检查本机出口公网 IPv4 和 IPv6。当检测到地址变化时，脚本会通过 SMTP 发送邮件通知，并把最新地址记录到本地状态文件中。

项目只使用 Python 标准库，不需要安装第三方依赖。

## 功能

- 分别获取公网 IPv4 和 IPv6
- 分别记录上次检测到的 IPv4 和 IPv6
- 首次运行只写入当前地址，不发送通知
- 地址变化后发送邮件通知
- IPv4 或 IPv6 某一项获取失败时，不影响另一项检查
- 支持 SMTP SSL 和 STARTTLS
- 支持源码运行，也兼容后续打包为可执行文件后的同目录配置

## 项目文件

```text
.
├─ ip_monitor.py        # 主程序
├─ config.example.ini   # 配置模板
├─ config.ini           # 本地真实配置，需自行从模板复制生成
├─ last_ipv4.txt        # 上次记录的公网 IPv4，运行后自动生成或更新
└─ last_ipv6.txt        # 上次记录的公网 IPv6，运行后自动生成或更新
```

## 环境要求

- Python 3.8 或更高版本

## 快速开始

### 1. 复制配置模板

Windows PowerShell：

```powershell
Copy-Item config.example.ini config.ini
```

Linux / macOS：

```bash
cp config.example.ini config.ini
```

### 2. 修改 `config.ini`

至少需要配置邮件相关信息：

```ini
[email]
to_addr = receiver@example.com
from_addr = sender@example.com
smtp_user = sender@example.com
smtp_password = your_smtp_password_or_app_code
smtp_host = smtp.example.com
smtp_port = 465
use_ssl = true
```

如果默认 IP 查询接口在你的网络环境中不可用，可以修改：

```ini
[monitor]
ipv4_url = https://api-ipv4.ip.sb/ip
ipv6_url = https://api-ipv6.ip.sb/ip
```

建议选择返回纯文本 IP 地址的接口。

### 3. 启动程序

```bash
python ip_monitor.py
```

程序启动后会持续运行，并按 `interval_minutes` 指定的间隔循环检查公网 IP。

## 配置说明

### `[monitor]`

`interval_minutes`

检查间隔，单位为分钟。必须大于 `0`。

`ipv4_url`

用于获取公网 IPv4 的接口地址。接口返回值必须是合法 IPv4，例如 `1.2.3.4`。

`ipv6_url`

用于获取公网 IPv6 的接口地址。接口返回值必须是合法 IPv6。

### `[email]`

`to_addr`

通知邮件收件人。

`from_addr`

通知邮件发件人地址。

`smtp_user`

SMTP 登录账号。

`smtp_password`

SMTP 登录密码或邮箱服务商提供的授权码。

`smtp_host`

SMTP 服务器地址。

`smtp_port`

SMTP 端口。常见取值为 `465` 或 `587`。

`use_ssl`

是否使用 SMTP SSL。

- `true`：使用 `SMTP_SSL`，通常搭配 `465`
- `false`：使用普通 SMTP 连接后执行 `STARTTLS`，通常搭配 `587`

## 运行逻辑

1. 程序启动后读取同目录下的 `config.ini`
2. 校验 `[monitor]` 和 `[email]` 配置段是否存在
3. 按配置分别请求 `ipv4_url` 和 `ipv6_url`
4. 校验接口返回值是否为对应版本的合法 IP 地址
5. 读取 `last_ipv4.txt` 和 `last_ipv6.txt`
6. 首次运行时只写入当前地址，不发送邮件
7. 后续运行时，如果 IPv4 或 IPv6 任一地址变化，则发送邮件
8. 邮件发送成功后更新对应状态文件
9. 等待 `interval_minutes` 后进入下一轮检查

## 状态文件

程序会在 `ip_monitor.py` 所在目录读写状态文件：

- `last_ipv4.txt`
- `last_ipv6.txt`

如果程序被打包成可执行文件，则配置文件和状态文件会按可执行文件所在目录解析。

## 异常处理

- IPv4 获取失败：记录警告，继续尝试 IPv6
- IPv6 获取失败：记录警告，继续处理 IPv4
- IPv4 和 IPv6 都获取失败：跳过本轮检查
- 邮件发送失败：记录错误，等待下一轮重试
- 配置文件缺失或配置不合法：启动失败并退出

## 安全注意事项

- 不要把真实 `config.ini` 提交到版本库
- 不要在公开仓库中暴露邮箱密码或 SMTP 授权码
- `last_ipv4.txt` 和 `last_ipv6.txt` 只是当前状态记录，不是完整变更审计日志

## 常见问题

### 为什么首次运行不发邮件？

首次运行没有历史地址可对比，因此程序只保存当前 IPv4/IPv6，避免发送没有实际变化意义的通知。

### 没有 IPv6 会怎样？

如果当前网络没有可用 IPv6，IPv6 获取会失败或返回非法值。程序会记录警告，但仍可继续监控 IPv4。

### 可以只监控 IPv4 吗？

当前程序会同时尝试 IPv4 和 IPv6。没有 IPv6 的环境可以保留 `ipv6_url` 默认值，程序会在 IPv6 获取失败时继续处理 IPv4。

## 许可证

当前仓库未提供许可证文件。如需开源分发，建议补充 `LICENSE`。
