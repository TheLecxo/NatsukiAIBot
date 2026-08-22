import os
import subprocess
import sys
import tkinter as tk

from src.utils.runtime_monitor import BASE_DIR


DASHBOARDS = (
    ("Errors", "errors", "Natsuki - Errors"),
    ("Bot Events", "events", "Natsuki - Bot Events"),
    ("Active Users", "users", "Natsuki - Active Users"),
    ("SERVICE HEALTH", "health", "Natsuki - Service Health"),
)


class ManagePanel:
    def __init__(self, root):
        self.root = root
        self.processes = []
        root.title("Natsuki - Manage")
        root.geometry("430x360")
        root.minsize(380, 320)
        root.configure(bg="#101820")
        root.protocol("WM_DELETE_WINDOW", self.close)

        title = tk.Label(
            root,
            text="NATSUKI | MANAGE",
            bg="#101820",
            fg="#f4f7f8",
            font=("Segoe UI", 18, "bold"),
            pady=20,
        )
        title.pack(fill="x")

        subtitle = tk.Label(
            root,
            text="Open a live runtime view in a new CMD window",
            bg="#101820",
            fg="#9fb3bd",
            font=("Segoe UI", 10),
            pady=2,
        )
        subtitle.pack(fill="x")

        grid = tk.Frame(root, bg="#101820", padx=24, pady=24)
        grid.pack(fill="both", expand=True)
        for index, (label, view, window_title) in enumerate(DASHBOARDS):
            button = tk.Button(
                grid,
                text=label,
                command=lambda selected_view=view, selected_title=window_title: self.open_dashboard(
                    selected_view, selected_title
                ),
                bg="#1c3540",
                fg="#f4f7f8",
                activebackground="#2b5968",
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground="#4f7d89",
                highlightcolor="#b5e8ef",
                font=("Segoe UI", 11, "bold"),
                cursor="hand2",
                padx=12,
                pady=16,
            )
            button.grid(row=index // 2, column=index % 2, sticky="nsew", padx=6, pady=6)

        for column in range(2):
            grid.columnconfigure(column, weight=1)
        for row in range(2):
            grid.rowconfigure(row, weight=1)

    def open_dashboard(self, view, title):
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "NATSUKI_CONSOLE_TITLE": title,
        }
        process = subprocess.Popen(
            [sys.executable, "-m", "src.utils.console_dashboard", view],
            cwd=str(BASE_DIR),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env=environment,
        )
        self.processes.append(process)

    def close(self):
        for process in self.processes:
            if process.poll() is None:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        self.root.destroy()


def main():
    root = tk.Tk()
    ManagePanel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
