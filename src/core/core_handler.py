
from pathlib import Path


class CoreHandler:
    def __init__(self, bot, core_path=".core/natsuki.chr"):
        self.bot = bot
        self.core_path = Path(core_path)
        self.core_path.parent.mkdir(parents=True, exist_ok=True)
        self.turn_on()

    def has_core_file(self):
        return self.core_path.exists() and self.core_path.is_file()

    def turn_on(self):
        self.core_path.parent.mkdir(parents=True, exist_ok=True)
        self.core_path.touch(exist_ok=True)

    def turn_off(self):
        self.core_path.parent.mkdir(parents=True, exist_ok=True)
        if self.core_path.exists():
            self.core_path.unlink()

    def is_on(self):
        return self.has_core_file()