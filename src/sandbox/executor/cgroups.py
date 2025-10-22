import os, time, signal, subprocess
from pathlib import Path
from typing import Dict, Optional

CGROOT = Path("/sys/fs/cgroup")
PARENT = CGROOT / "sbx"

def _is_v2() -> bool:
    return (CGROOT / "cgroup.controllers").exists()

def _read(path: Path) -> str:
    return path.read_text().strip() if path.exists() else ""

def _write(path: Path, data: str):
    path.write_text(data)

def _ensure_parent():
    PARENT.mkdir(exist_ok=True)
    # Bật controllers ở parent
    avail = _read(CGROOT / "cgroup.controllers").split()
    stree = PARENT / "cgroup.subtree_control"
    cur = _read(stree).split()
    want = ["cpu", "memory", "pids"]  # + "io" nếu cần
    for c in want:
        if c in avail and f"+{c}" not in cur:
            with open(stree, "w") as f:
                f.write(f"+{c}\n")

def create_leaf(job_id: str) -> Path:
    if not _is_v2():
        raise RuntimeError("Cgroup v2 unified not available")
    _ensure_parent()
    leaf = PARENT / job_id
    leaf.mkdir(exist_ok=True)
    return leaf

def set_memory(leaf: Path, max_: str, swap_max: str = "0", oom_group: bool = True):
    _write(leaf / "memory.max", str(max_))
    _write(leaf / "memory.swap.max", str(swap_max))
    _write(leaf / "memory.oom.group", "1" if oom_group else "0")

def set_cpu_max(leaf: Path, cpu_max: Optional[str] = None, weight: Optional[int] = None):
    # Dùng 1 trong 2
    if cpu_max:
        _write(leaf / "cpu.max", cpu_max)      # e.g., "100000 100000" = 1 core
    if weight:
        _write(leaf / "cpu.weight", str(int(weight)))  # 1..10000

def set_pids(leaf: Path, max_pids: int):
    _write(leaf / "pids.max", str(int(max_pids)))

def set_io(leaf: Path, device: str, rbytes: Optional[str], wbytes: Optional[str]):
    """
    device: "major:minor" (vd "8:0" cho /dev/sda); yêu cầu controller io bật ở parent.
    rbytes/wbytes: bytes per second, ví dụ "52428800" (50MB/s). Dùng 'max' để bỏ hạn chế.
    """
    # io.max format: "major:minor rbps=... wbps=..."
    # Kiểm tra tồn tại controller io
    stree = PARENT / "cgroup.subtree_control"
    cur = _read(stree)
    if "+io" not in cur:
        # thử bật io nếu kernel cho phép
        avail = _read(CGROOT / "cgroup.controllers").split()
        if "io" in avail:
            with open(stree, "w") as f:
                f.write("+io\n")
        else:
            raise RuntimeError("IO controller not available on this kernel")

    fields = []
    if rbytes: fields.append(f"rbps={rbytes}")
    if wbytes: fields.append(f"wbps={wbytes}")
    line = f"{device} " + " ".join(fields) if fields else f"{device}"
    # Có thể cần nhiều dòng cho nhiều thiết bị
    with open(leaf / "io.max", "w") as f:
        f.write(line + "\n")

def attach_pid(leaf: Path, pid: int):
    _write(leaf / "cgroup.procs", str(int(pid)))

def kill_and_cleanup(leaf: Path, wait_s: float = 3.0):
    ck = leaf / "cgroup.kill"
    if ck.exists():
        _write(ck, "1")
    else:
        # Fallback: kill tất cả PIDs trong nhóm
        pids = _read(leaf / "cgroup.procs").split()
        for p in pids:
            try: os.kill(int(p), signal.SIGKILL)
            except ProcessLookupError: pass

    # Chờ đến khi trống
    t0 = time.time()
    events = leaf / "cgroup.events"
    while time.time() - t0 < wait_s:
        txt = _read(events)
        if "populated=0" in txt:
            break
        time.sleep(0.05)

    # Thử xoá
    try: leaf.rmdir()
    except OSError:
        # Có thể bận; đợi thêm chút rồi thử lại
        time.sleep(0.1)
        try: leaf.rmdir()
        except OSError:
            pass

def read_metrics(leaf: Path) -> Dict[str, str]:
    out = {}
    for name in ["memory.current", "memory.events", "cpu.stat", "pids.current"]:
        p = leaf / name
        if p.exists():
            out[name] = p.read_text().strip()
    return out
