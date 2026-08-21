import os
import sys
from urllib.parse import urlsplit


def _normalize_proxy(proxy):
    proxy = proxy.strip()
    if not proxy:
        return None

    if "://" not in proxy:
        proxy = f"http://{proxy}"

    try:
        parsed = urlsplit(proxy)
        port = parsed.port
    except ValueError:
        return None

    if not parsed.hostname or not port:
        return None

    return proxy


def _proxy_from_windows_settings():
    if sys.platform != "win32":
        return None

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            enabled = winreg.QueryValueEx(key, "ProxyEnable")[0]
            proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
    except (FileNotFoundError, OSError):
        return None

    if not enabled or not proxy_server:
        return None

    entries = {}
    for item in str(proxy_server).split(";"):
        if "=" in item:
            scheme, value = item.split("=", 1)
            entries[scheme.strip().lower()] = value.strip()
        else:
            entries["default"] = item.strip()

    return _normalize_proxy(
        entries.get("https") or entries.get("http") or entries.get("default")
    )


def get_system_proxy():
    """Return the configured HTTP proxy for Telegram, or None if unavailable."""
    for variable in ("TELEGRAM_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        proxy = _normalize_proxy(os.getenv(variable, ""))
        if proxy:
            return proxy

    return _proxy_from_windows_settings()