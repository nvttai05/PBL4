import subprocess
from pathlib import Path
from typing import Dict, Any

def run_in_sandbox(
    job_dir: Path,
    entry_py: str,
    rootfs: Path,
    timeout_s: int = 8,
    *,
    noexec_work: bool = False,   # True: /work R/W nhưng chặn exec
    enable_loopback: bool = False,   # True: bật lo (127.0.0.1), vẫn không outbound
    bind_full_etc: bool = True,      # False: bind tối thiểu /etc/* cần thiết
) -> Dict[str, Any]:
    """
    Chạy entry_py (nằm trong job_dir) trong sandbox (NS + chroot) theo chuẩn GĐ3.
    - job_dir: thư mục chứa code + IO của job (bind R/W vào /work)
    - entry_py: tên file, ví dụ "main.py"
    - rootfs: thư mục rootfs (khung), ví dụ /srv/sbx/rootfs
    - timeout_s: timeout tổng cho unshare + job
    - noexec_work: siết /work không cho exec (phù hợp job Python thuần)
    - enable_loopback: nếu lib cần 127.0.0.1 (vẫn offline vì không route/DNS)
    - bind_full_etc: bind toàn bộ /etc (RO) hoặc chỉ file tối thiểu (RO)
    """

    # Flags cho /work
    work_flags = "rw,nosuid,nodev" + (",noexec" if noexec_work else "")

    # /etc: bind cả cây (RO) hay chỉ file tối thiểu (RO)
    etc_block = f"""
# /etc (RO) — bản đầy đủ hoặc tối thiểu
mkdir -p {rootfs}/etc
"""
    if bind_full_etc:
        etc_block += f"""
mount --bind /etc {rootfs}/etc
mount -o remount,bind,ro {rootfs}/etc
"""
    else:
        etc_block += f"""
for f in hosts nsswitch.conf ld.so.cache localtime; do
  if [ -f /etc/$f ]; then
    mkdir -p $(dirname {rootfs}/etc/$f)
    mount --bind /etc/$f {rootfs}/etc/$f
    mount -o remount,bind,ro {rootfs}/etc/$f
  fi
done
"""

    # (tuỳ) bật loopback nội bộ
    net_block = "true"
    if enable_loopback:
        net_block = "ip link set lo up || true"

    ns_script = f"""
set -euo pipefail

# [0] Chặn propagation: không rò mount ra host/NS khác
mount --make-rprivate /

# [1] Chuẩn bị cây rootfs
mkdir -p {rootfs}/{{proc,tmp,usr,lib,lib64,bin,work,dev}}
# (tùy distro) có thể cần nhánh thư viện kiểu Debian/Ubuntu
[ -d /lib/x86_64-linux-gnu ] && mkdir -p {rootfs}/lib/x86_64-linux-gnu

# [2] /tmp riêng (an toàn)
mount -t tmpfs -o nosuid,nodev,noexec,size=256M tmpfs {rootfs}/tmp

# [3] /proc phù hợp PID-NS (mount vào rootfs để thấy trong chroot)
mount -t proc none {rootfs}/proc

# [4] Bind RO hạ tầng Python (có remount,bind,ro)
mount --bind /usr {rootfs}/usr
mount -o remount,bind,ro {rootfs}/usr

mount --bind /lib {rootfs}/lib || true
mount -o remount,bind,ro {rootfs}/lib || true

mount --bind /lib64 {rootfs}/lib64 || true
mount -o remount,bind,ro {rootfs}/lib64 || true

if [ -d /lib/x86_64-linux-gnu ]; then
  mount --bind /lib/x86_64-linux-gnu {rootfs}/lib/x86_64-linux-gnu
  mount -o remount,bind,ro {rootfs}/lib/x86_64-linux-gnu
fi

# /bin (RO) để chắc có shell khi chroot
mount --bind /bin {rootfs}/bin || true
mount -o remount,bind,ro {rootfs}/bin || true

# /dev tối thiểu (RO) — chỉ khi cần
for d in null zero urandom; do
  if [ -e /dev/$d ]; then
    touch {rootfs}/dev/$d || true
    mount --bind /dev/$d {rootfs}/dev/$d || true
    mount -o remount,bind,ro {rootfs}/dev/$d || true
  fi
done

# [4c] /etc (RO): đầy đủ hoặc tối thiểu
{etc_block}

# [5] Bind R/W job vào /work (siết nosuid,nodev và tùy chọn noexec)
mkdir -p {rootfs}/work
mount --bind {job_dir} {rootfs}/work
mount -o remount,bind,{work_flags} {rootfs}/work

# [5b] Network NS mặc định offline; (tuỳ) bật loopback local-only
{net_block}

# [6] Vào chroot, cd /, chạy Python
chroot {rootfs} /usr/bin/env bash -lc '
  set -euo pipefail
  cd /
  umask 002
  exec /usr/bin/python3 "/work/{entry_py}"
'
"""

    cmd = [
        "unshare",
        "--fork", "--pid", "--mount", "--net", "--uts",
        "--user", "--map-root-user",  # root ảo trong NS
        "bash", "-lc", ns_script
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        return {
            "status": "finished",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "returncode": None, "stdout": "", "stderr": f"Timeout exceeded: {timeout_s}s"}
    except Exception as e:
        return {"status": "error", "returncode": None, "stdout": "", "stderr": str(e)}
# Example usage:
if __name__ == "__main__":
    rootfs = Path("/srv/sbx/rootfs")
    job_dir = Path("/srv/sbx/jobs/ABC123")
    res = run_in_sandbox(job_dir, "main.py", rootfs,
                         timeout_s=8,
                         noexec_work=True,       # Python thuần: bật an toàn
                         enable_loopback=False,  # mặc định offline tuyệt đối
                         bind_full_etc=True)     # hoặc False nếu muốn tối thiểu
    print(res["status"], res["returncode"])
    print(res["stdout"])
    print(res["stderr"])
    # lệnh chạy
    # (.venv) ➜  sandbox
    # export
    # PYTHONPATH = src
    # python - m
    # sandbox.cli
    # run - phase3 - -job
    # JOB1 - -entry
    # main.py - -timeout
    # 8

