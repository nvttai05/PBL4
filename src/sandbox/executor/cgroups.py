import os
import time
import subprocess
from pathlib import Path
from typing import Optional, Dict

CGROUP_ROOT = Path("/sys/fs/cgroup")

def check_cgroupv2() -> bool:
    return (CGROUP_ROOT / "cgroup.controllers").exists()

def create_cgroup(name: str) -> Path:
    cg_path = CGROUP_ROOT / name
    cg_path.mkdir(exist_ok=True)
    return cg_path

def enable_controllers(controllers=("cpu", "memory", "pids")) -> None:
    """Bật controller cho root cgroup."""
    ctrl_file = CGROUP_ROOT / "cgroup.controllers"
    avail = ctrl_file.read_text().split()
    stree = CGROUP_ROOT / "cgroup.subtree_control"
    current = stree.read_text().split()
    for c in controllers:
        if c in avail and f"+{c}" not in current:
            try:
                with open(stree, "a") as f:  # append thay vì overwrite
                    f.write(" +" + c)
            except Exception as e:
                print(f"[warn] Không thể bật controller {c}: {e}")

def set_memory_limit(cg_path: Path, bytes_limit: Optional[int]) -> None:
    val = "max" if bytes_limit is None else str(bytes_limit)
    (cg_path / "memory.max").write_text(val)
    (cg_path / "memory.swap.max").write_text("0")   
    (cg_path / "memory.oom.group").write_text("0")  

def set_cpu_limit(cg_path: Path, max_usec: int, period_usec: int = 100000) -> None:
    (cg_path / "cpu.max").write_text(f"{max_usec} {period_usec}")

def set_pids_limit(cg_path: Path, n: int) -> None:
    (cg_path / "pids.max").write_text(str(n))

def add_pid(cg_path: Path, pid: int) -> None:
    (cg_path / "cgroup.procs").write_text(str(pid))

def cleanup_cgroup(cg_path: Path) -> None:
    """Đưa tiến trình về root và xóa cgroup."""
    try:
        procs_file = cg_path / "cgroup.procs"
        if procs_file.exists():
            for pid in procs_file.read_text().split():
                (CGROUP_ROOT / "cgroup.procs").write_text(pid)
        time.sleep(1)
        cg_path.rmdir()
    except Exception as e:
        print("Cleanup lỗi:", e)

def read_stats(cg_path: Path) -> Dict[str, str]:
    info = {}
    for f in ["memory.current", "cpu.stat", "pids.current"]:
        p = cg_path / f
        if p.exists():
            info[f] = p.read_text().strip()
    return info

def busy_cpu(duration_s: int):
    end = time.time() + duration_s
    while time.time() < end:
        for i in range(10000):
            _ = i * i

def busy_mem(mb: int):
    print(f"[child] Allocating {mb} MB...")
    data = []
    try:
        for i in range(mb):
            data.append(bytearray(1024 * 1024))
            for j in range(0, 1024 * 1024, 4096):
                data[i][j] = 1
            print(f"[child] touched {i+1} MB")
            time.sleep(0.02)
    except MemoryError:
        print("[child] MemoryError xảy ra!")
    finally:
        print("[child] done")

def run_test(cg_path: Path, mode: str):
    p = subprocess.Popen(["python3", __file__, "--child", mode])
    add_pid(cg_path, p.pid)
    p.wait()
    print("[parent] child exited with", p.returncode)

def main():
    if "--child" in os.sys.argv:
        idx = os.sys.argv.index("--child")
        mode = os.sys.argv[idx + 1]
        if mode == "cpu":
            busy_cpu(5)
        elif mode == "mem":
            busy_mem(300)
        return

    if os.geteuid() != 0:
        print("Cần chạy bằng sudo: sudo python3", __file__)
        os.sys.exit(1)

    if not check_cgroupv2():
        print("Hệ thống không hỗ trợ cgroup v2.")
        os.sys.exit(1)

    name = "tuandeptrai"
    cg_path = create_cgroup(name)
    enable_controllers()
    print(f"Tạo cgroup: {cg_path}")

    try:
        set_memory_limit(cg_path, 256 * 1024 * 1024)  # 256MB thực sự
        set_cpu_limit(cg_path, 50000, 100000)
        set_pids_limit(cg_path, 8)

        print("\n--- RUN CPU TEST ---")
        run_test(cg_path, "cpu")

        print("\n--- RUN MEM TEST ---")
        run_test(cg_path, "mem")

        print("\n--- THỐNG KÊ SAU KHI TEST ---")
        stats = read_stats(cg_path)
        for k, v in stats.items():
            print(f"{k}: {v}")

    finally:
        print("Dọn dẹp cgroup...")
        # cleanup_cgroup(cg_path)
        print("Hoàn tất.")

if __name__ == "__main__":
    main()
