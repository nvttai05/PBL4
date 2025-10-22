import yaml
from pathlib import Path
from typing import Any, Dict

def load_limits(conf_path: str = "conf/limits.yaml") -> Dict[str, Any]:
    p = Path(conf_path)
    if not p.exists():
        return {"enabled": False}
    with p.open() as f:
        return yaml.safe_load(f) or {"enabled": False}
