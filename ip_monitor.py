#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import logging
import os
import smtplib
import ssl
import sys
import time
from email.mime.text import MIMEText
from email.header import Header
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")
LAST_IP_FILE = os.path.join(BASE_DIR, "last_ip.txt")


def load_config(config_path: str) -> configparser.ConfigParser:
    """加载配置文件。"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")

    required_sections = ["monitor", "email"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"配置文件缺少 [{section}] 段")

    return config


def setup_logging() -> None:
    """初始化日志。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def get_public_ip(ip_service_url: str, timeout: int = 10) -> str:
    """
    获取公网 IP。
    建议配置返回纯文本 IP 的服务，例如:
    - https://api.ipify.org
    - https://ifconfig.me/ip
    """
    req = Request(
        ip_service_url,
        headers={
            "User-Agent": "Mozilla/5.0 (IP-Monitor/1.0)"
        }
    )

    with urlopen(req, timeout=timeout) as response:
        ip = response.read().decode("utf-8").strip()

    if not ip:
        raise ValueError("获取到的公网 IP 为空")

    return ip


def read_last_ip(file_path: str) -> str:
    """读取上一次记录的 IP，不存在则返回空字符串。"""
    if not os.path.exists(file_path):
        return ""

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_last_ip(file_path: str, ip: str) -> None:
    """保存当前 IP。"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(ip)


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    use_ssl: bool = True
) -> None:
    """通过 SMTP 发送邮件。"""

    from email.utils import formataddr
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = formataddr(("IP监控", from_addr))
    msg["To"] = formataddr(("通知接收", to_addr))
    msg["Subject"] = Header(subject, "utf-8")

    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=20) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, [to_addr], msg.as_string())


def check_and_notify(config: configparser.ConfigParser) -> None:
    """检查公网 IP 是否变化，变化则发邮件。"""
    interval_minutes = config.getint("monitor", "interval_minutes", fallback=60)
    ip_service_url = config.get("monitor", "ip_service_url", fallback="https://api.ipify.org")

    to_addr = config.get("email", "to_addr")
    from_addr = config.get("email", "from_addr")
    smtp_user = config.get("email", "smtp_user")
    smtp_password = config.get("email", "smtp_password")
    smtp_host = config.get("email", "smtp_host")
    smtp_port = config.getint("email", "smtp_port", fallback=465)
    use_ssl = config.getboolean("email", "use_ssl", fallback=True)

    logging.info("开始检查公网 IP ...")
    current_ip = get_public_ip(ip_service_url)
    last_ip = read_last_ip(LAST_IP_FILE)

    logging.info("当前公网 IP: %s", current_ip)
    logging.info("上次记录 IP: %s", last_ip if last_ip else "(无记录)")

    # 首次运行：只记录，不发邮件
    if not last_ip:
        save_last_ip(LAST_IP_FILE, current_ip)
        logging.info("首次运行，已记录当前 IP，不发送通知邮件。")
        return

    if current_ip != last_ip:
        subject = "公网 IP 变更通知"
        body = (
            f"检测到公网 IP 已变更。\n\n"
            f"旧 IP: {last_ip}\n"
            f"新 IP: {current_ip}\n"
        )

        send_email(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            from_addr=from_addr,
            to_addr=to_addr,
            subject=subject,
            body=body,
            use_ssl=use_ssl
        )

        save_last_ip(LAST_IP_FILE, current_ip)
        logging.info("公网 IP 发生变化，邮件已发送。")
    else:
        logging.info("公网 IP 未变化，无需发送邮件。")

    logging.info("下次检查间隔: %s 分钟", interval_minutes)


def main() -> None:
    setup_logging()

    try:
        config = load_config(CONFIG_FILE)
        interval_minutes = config.getint("monitor", "interval_minutes", fallback=60)

        if interval_minutes <= 0:
            raise ValueError("interval_minutes 必须大于 0")

        logging.info("IP 监控程序启动，轮询间隔 %d 分钟。", interval_minutes)

        while True:
            try:
                check_and_notify(config)
            except (URLError, HTTPError) as e:
                logging.error("获取公网 IP 失败: %s", e)
            except smtplib.SMTPException as e:
                logging.error("发送邮件失败: %s", e)
            except Exception as e:
                logging.exception("执行过程中出现异常: %s", e)

            time.sleep(interval_minutes * 60)

    except Exception as e:
        logging.exception("程序启动失败: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()