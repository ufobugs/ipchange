# IP 变更监控工具

这是一个使用 Python 标准库实现的公网 IP 监控脚本。程序会定时访问一个公网 IP 查询接口，对比当前 IP 和上一次记录的 IP；如果检测到变化，就通过 SMTP 发送邮件通知。

项目当前非常轻量，核心逻辑全部集中在 `ip_monitor.py` 中，适合直接运行，也便于后续打包成可执行文件使用。

## 功能特点

- 定时轮询公网 IP
- 首次运行只记录 IP，不发送通知
- 检测到 IP 变化时自动发送邮件
- 使用本地文件保存上一次 IP
- 仅依赖 Python 标准库，无需安装第三方包

## 项目结构

```text
.
├─ ip_monitor.py        # 主程序，包含监控、比较、通知等全部逻辑
├─ config.example.ini   # 配置模板
├─ config.ini           # 运行配置（由模板复制后按需修改）
└─ last_ip.txt          # 上一次记录的公网 IP（运行后自动生成/更新）
```

## 运行环境

- Python 3.8 及以上

理论上只要 Python 标准库可用即可运行，因为脚本没有依赖第三方包。

## 快速开始

### 1. 生成配置文件

首次使用请先复制模板：

```bash
cp config.example.ini config.ini
```

Windows PowerShell 可使用：

```powershell
Copy-Item config.example.ini config.ini
```

### 2. 配置 `config.ini`

配置文件包含两个 section：

- `[monitor]`：监控相关配置
- `[email]`：邮件发送相关配置

示例：

```ini
[monitor]
interval_minutes = 60
ip_service_url = https://ifconfig.me/ip

[email]
to_addr = your_receiver@example.com
from_addr = your_sender@example.com
smtp_user = your_sender@example.com
smtp_password = your_smtp_password
smtp_host = smtp.example.com
smtp_port = 465
use_ssl = true
```

### 3. 启动脚本

```bash
python ip_monitor.py
```

程序启动后会持续运行，并按 `interval_minutes` 指定的间隔循环检查公网 IP。

## 配置说明

### `[monitor]`

- `interval_minutes`
  - 检查间隔，单位为分钟
  - 程序启动时会校验，必须大于 0
- `ip_service_url`
  - 用于获取公网 IP 的 HTTP 地址
  - 建议返回纯文本 IP，例如：
    - `https://api.ipify.org`
    - `https://ifconfig.me/ip`

### `[email]`

- `to_addr`
  - 收件人邮箱
- `from_addr`
  - 发件人邮箱
- `smtp_user`
  - SMTP 登录账号
- `smtp_password`
  - SMTP 密码或授权码
- `smtp_host`
  - SMTP 服务器地址
- `smtp_port`
  - SMTP 端口
  - 常见为 `465` 或 `587`
- `use_ssl`
  - 是否使用 SSL
  - 通常 `465` 对应 `true`
  - 如果使用 `587`，一般设为 `false`，程序会走 `STARTTLS`

## 工作流程

程序执行流程如下：

1. 启动 `ip_monitor.py`
2. 初始化日志输出
3. 读取 `config.ini`
4. 校验轮询间隔是否合法
5. 进入无限循环
6. 请求 `ip_service_url` 获取当前公网 IP
7. 读取 `last_ip.txt` 中保存的历史 IP
8. 比较当前 IP 和历史 IP
9. 若首次运行，则只保存 IP，不发邮件
10. 若 IP 发生变化，则发送通知邮件并更新 `last_ip.txt`
11. 若 IP 未变化，则记录日志并等待下一轮

## 代码结构说明

`ip_monitor.py` 中的主要函数：

- `load_config(config_path)`
  - 加载并校验配置文件
- `setup_logging()`
  - 初始化日志格式和输出
- `get_public_ip(ip_service_url, timeout=10)`
  - 从公网接口获取当前 IP
- `read_last_ip(file_path)`
  - 读取上次记录的 IP
- `save_last_ip(file_path, ip)`
  - 保存当前 IP
- `send_email(...)`
  - 通过 SMTP 发送通知邮件
- `check_and_notify(config)`
  - 执行一次完整的“检查并通知”流程
- `main()`
  - 程序入口，负责循环调度

## 日志与状态文件

- 日志默认输出到标准输出
- `last_ip.txt` 用于保存最近一次成功记录的公网 IP

首次运行时，如果 `last_ip.txt` 不存在，程序会自动创建并写入当前 IP。
此外，`config.ini` 和 `last_ip.txt` 都按程序所在目录解析（源码运行与打包后运行都一致）。

## 异常处理

主循环中对常见异常做了捕获，避免程序因临时错误直接退出：

- 获取公网 IP 失败：捕获 `URLError`、`HTTPError`
- SMTP 发送失败：捕获 `smtplib.SMTPException`
- 其他异常：统一记录堆栈日志

如果启动阶段就出现严重错误，例如配置文件缺失或格式不合法，程序会记录错误并退出。

## 部署说明

脚本通过下面的逻辑计算运行目录：

- 普通脚本运行时使用当前文件路径
- 若程序被打包为可执行文件，则优先使用 `sys.executable`

这意味着 `config.ini` 和 `last_ip.txt` 默认按“与程序放在同一目录”来查找，便于后续打包部署。

## 安全注意事项

- 不建议把真实邮箱密码或 SMTP 授权码直接提交到版本库
- 更推荐把敏感信息改为环境变量或部署时注入
- `last_ip.txt` 仅保存最近一次 IP，不适合作为审计日志

## 可改进方向

- 增加命令行参数支持
- 增加日志文件输出
- 增加多收件人支持
- 增加失败重试机制
- 增加历史 IP 变更记录
- 增加 systemd / Windows 服务化部署说明

## 许可证

当前仓库未提供许可证文件。如需开源分发，建议补充 `LICENSE`。
