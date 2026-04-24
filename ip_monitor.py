#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import ipaddress
import logging
import os
import smtplib
import ssl
import sys
import time
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


BASE_DIR = os.path.dirname(
    os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
)

CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")
LAST_IPV4_FILE = os.path.join(BASE_DIR, "last_ipv4.txt")
LAST_IPV6_FILE = os.path.join(BASE_DIR, "last_ipv6.txt")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def load_config(config_path: str) -> configparser.ConfigParser:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")

    if "monitor" not in config or "email" not in config:
        raise ValueError("配置文件必须包含 [monitor] 和 [email] 段")

    return config


def get_ip_from_url(url: str, timeout: int = 10) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (IP-Monitor/1.0)"
        }
    )
    with urlopen(req, timeout=timeout) as response:
        value = response.read().decode("utf-8").strip()
        if not value:
            raise ValueError(f"接口返回为空: {url}")
        return value


def validate_ip(ip_str: str, version: int) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return ip_obj.version == version
    except ValueError:
        return False


def read_last_value(file_path: str) -> str:
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_value(file_path: str, value: str) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(value)


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


def get_current_ips(config: configparser.ConfigParser) -> tuple[str, str]:
    ipv4_url = config.get("monitor", "ipv4_url", fallback="https://api.ipify.org")
    ipv6_url = config.get("monitor", "ipv6_url", fallback="https://api64.ipify.org")

    current_ipv4 = ""
    current_ipv6 = ""

    try:
        ip = get_ip_from_url(ipv4_url)
        if validate_ip(ip, 4):
            current_ipv4 = ip
        else:
            logging.warning("IPv4 接口返回的不是合法 IPv4: %s", ip)
    except Exception as e:
        logging.warning("获取 IPv4 失败: %s", e)

    try:
        ip = get_ip_from_url(ipv6_url)
        if validate_ip(ip, 6):
            current_ipv6 = ip
        else:
            logging.warning("IPv6 接口返回的不是合法 IPv6: %s", ip)
    except Exception as e:
        logging.warning("获取 IPv6 失败: %s", e)

    return current_ipv4, current_ipv6


def check_and_notify(config: configparser.ConfigParser) -> None:
    interval_minutes = config.getint("monitor", "interval_minutes", fallback=60)

    to_addr = config.get("email", "to_addr")
    from_addr = config.get("email", "from_addr")
    smtp_user = config.get("email", "smtp_user")
    smtp_password = config.get("email", "smtp_password")
    smtp_host = config.get("email", "smtp_host")
    smtp_port = config.getint("email", "smtp_port", fallback=465)
    use_ssl = config.getboolean("email", "use_ssl", fallback=True)

    logging.info("开始检查公网 IPv4 / IPv6 ...")

    current_ipv4, current_ipv6 = get_current_ips(config)
    last_ipv4 = read_last_value(LAST_IPV4_FILE)
    last_ipv6 = read_last_value(LAST_IPV6_FILE)

    logging.info("当前 IPv4: %s", current_ipv4 or "(未获取到)")
    logging.info("当前 IPv6: %s", current_ipv6 or "(未获取到)")
    logging.info("上次 IPv4: %s", last_ipv4 or "(无记录)")
    logging.info("上次 IPv6: %s", last_ipv6 or "(无记录)")

    if not current_ipv4 and not current_ipv6:
        logging.warning("本次 IPv4 和 IPv6 都未获取到，跳过。")
        return

    # 首次运行：只记录，不发邮件
    if not last_ipv4 and not last_ipv6:
        if current_ipv4:
            save_value(LAST_IPV4_FILE, current_ipv4)
        if current_ipv6:
            save_value(LAST_IPV6_FILE, current_ipv6)
        logging.info("首次运行，已记录当前 IPv4/IPv6，不发送通知邮件。")
        return

    ipv4_changed = current_ipv4 and (current_ipv4 != last_ipv4)
    ipv6_changed = current_ipv6 and (current_ipv6 != last_ipv6)

    if ipv4_changed or ipv6_changed:
        subject = "公网 IP 变更通知"

        lines = ["检测到公网 IP 发生变化。", ""]

        if ipv4_changed:
            lines.append(f"IPv4 旧值: {last_ipv4 or '(无记录)'}")
            lines.append(f"IPv4 新值: {current_ipv4}")
            lines.append("")

        if ipv6_changed:
            lines.append(f"IPv6 旧值: {last_ipv6 or '(无记录)'}")
            lines.append(f"IPv6 新值: {current_ipv6}")
            lines.append("")

        lines.append("当前完整状态：")
        lines.append(f"IPv4: {current_ipv4 or '(未获取到)'}")
        lines.append(f"IPv6: {current_ipv6 or '(未获取到)'}")

        body = "\n".join(lines)

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

        if current_ipv4:
            save_value(LAST_IPV4_FILE, current_ipv4)
        if current_ipv6:
            save_value(LAST_IPV6_FILE, current_ipv6)

        logging.info("IPv4/IPv6 发生变化，邮件已发送。")
    else:
        logging.info("IPv4/IPv6 未变化，无需发送邮件。")

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
                logging.error("网络请求失败: %s", e)
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