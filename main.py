#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import io
import warnings
import asyncio
import queue
import threading
import os

try:
    import msvcrt
except ImportError:
    msvcrt = None

os.environ.setdefault("NATSUKI_MAIN_CONSOLE", "1")

# تعیین UTF-8 برای Windows Console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.utils.logger import setup_logger
from src.telegram.bot_handler import start_bot
from src.utils.runtime_monitor import (
    initialize_runtime,
    set_bot_state,
    record_event,
    start_dashboards,
    stop_dashboards,
)

warnings.filterwarnings("ignore")

def _read_console_commands(command_queue, ready_event):
    ready_event.wait()
    print("- Bot is Polling: Ready to receive updates.")
    print("- Press r to restart the bot and apply the latest changes.")
    print("- Press y to shut down the bot completely and close all CMD windows.")
    print("Control command [y=shutdown, r=restart]: ", end="", flush=True)
    while True:
        try:
            if msvcrt is not None:
                command = msvcrt.getwch().lower()
                print(command, flush=True)
            else:
                command = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            command = "y"
        if command in {"y", "r"}:
            command_queue.put(command)
            return


def main():
    """نقطه ورود اصلی برنامه"""
    logger = setup_logger()
    logger.info("=" * 50)
    logger.info("Starting Natsuki Bot...")
    logger.info("=" * 50)
    initialize_runtime()
    start_dashboards()
    command_queue = queue.Queue()
    control_ready = threading.Event()
    command_thread = threading.Thread(
        target=_read_console_commands,
        args=(command_queue, control_ready),
        daemon=True,
    )
    command_thread.start()

    try:
        result = asyncio.run(start_bot(command_queue, control_ready))
        stop_dashboards()
        if result == "restart":
            set_bot_state("restarting", "Restart requested from the main console")
            record_event("restart_requested", "The bot is restarting to apply the latest changes")
            os.execv(sys.executable, [sys.executable, *sys.argv])
    except KeyboardInterrupt:
        stop_dashboards()
        set_bot_state("stopped", "Interrupted by the operator")
        logger.info("Bot stopped by user")
    except Exception as e:
        stop_dashboards()
        set_bot_state("error", str(e))
        record_event("fatal_error", str(e), level="ERROR")
        logger.critical(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    main()
