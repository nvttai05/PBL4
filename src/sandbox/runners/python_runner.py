from dataclasses import dataclass
from pathlib import Path

@dataclass
class PythonJob:
    job_dir: Path
    entry: str

def build(job: PythonJob) -> bool:
    # Python là thông dịch — không cần build
    return True

def command(job: PythonJob) -> list[str]:
    # Dùng bởi executor khác nếu cần; với GĐ3 ta chạy trực tiếp trong chroot như đã viết
    return ["/usr/bin/python3", f"/work/{job.entry}"]
