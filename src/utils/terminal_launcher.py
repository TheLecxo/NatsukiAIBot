import os
import shutil
import subprocess


def open_history_terminal(user_id, title, base_dir, python_executable):
    if os.name != "nt":
        return False, "Windows Terminal is available only on Windows."

    try:
        executable = shutil.which("wt.exe") or shutil.which("wt")
        if not executable:
            return False, "Windows Terminal is not installed or its wt.exe alias is disabled."

        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        subprocess.Popen(
            [
                executable,
                "new-tab",
                "--title",
                f"Natsuki Chat - {title}",
                python_executable,
                "-X",
                "utf8",
                "-m",
                "src.utils.console_history",
                str(user_id),
            ],
            cwd=str(base_dir),
            env=environment,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    except OSError as error:
        return False, f"Windows Terminal could not be opened: {error}"
    return True, f"Chat history opened for user {user_id}."
