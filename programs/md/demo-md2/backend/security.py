"""SSRF 防护工具：校验目标 URL 不指向内网/回环/链路本地地址。"""
import ipaddress
import socket
from urllib.parse import urlparse


def is_blocked_ip(ip_str: str) -> bool:
    """判断 IP 是否为内网/回环/链路本地等不可达外网地址。"""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def is_ssrf_url(url: str) -> bool:
    """检查 URL 是否指向内网/回环地址（SSRF 防护）。返回 True 表示应拒绝。"""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return True
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            return True
        for info in infos:
            ip_str = info[4][0]
            if is_blocked_ip(ip_str):
                return True
        return False
    except Exception:
        return True
