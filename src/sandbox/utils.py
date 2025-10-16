# tiện ích: quote path, run_subprocess
import subprocess, shlex

def q(p: str) -> str:
    return shlex.quote(p)

def run(cmd: list[str] | str, timeout: int = 8):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
