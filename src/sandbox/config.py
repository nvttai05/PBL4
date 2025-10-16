# load conf/*
from pathlib import Path
import os, yaml

def load_config(path: str | None = None) -> dict:
    cfg_path = Path(path or os.environ.get("SANDBOX_CONF", "conf/sandbox.yaml"))
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

class Settings:
    def __init__(self, d: dict):
        self.rootfs = Path(d["rootfs"])
        self.jobs_dir = Path(d["jobs_dir"])
        self.defaults = d.get("defaults", {})
