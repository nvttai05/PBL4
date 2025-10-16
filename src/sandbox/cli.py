# CLI: run-phase3 ...
import json, argparse
from pathlib import Path
from .config import load_config, Settings
from .executor.ns_chroot import run_in_sandbox

def parse_args():
    p = argparse.ArgumentParser("sandbox")
    sub = p.add_subparsers(dest="cmd", required=True)

    r3 = sub.add_parser("run-phase3", help="Run in namespaces + chroot (GĐ3)")
    r3.add_argument("--job", required=True)
    r3.add_argument("--entry", required=True)
    r3.add_argument("--timeout", type=int)
    r3.add_argument("--noexec-work", action="store_true")
    r3.add_argument("--enable-loopback", action="store_true")
    r3.add_argument("--bind-full-etc", action="store_true")
    r3.add_argument("--conf", default="conf/sandbox.yaml")
    return p.parse_args()

def main():
    args = parse_args()
    cfg = Settings(load_config(args.conf))
    job_dir = cfg.jobs_dir / args.job
    rootfs = cfg.rootfs
    timeout = args.timeout or cfg.defaults.get("timeout_s", 8)

    res = run_in_sandbox(
        job_dir=job_dir,
        entry_py=args.entry,
        rootfs=rootfs,
        timeout_s=timeout,
        noexec_work=args.noexec_work or cfg.defaults.get("noexec_work", True),
        enable_loopback=args.enable_loopback or cfg.defaults.get("enable_loopback", False),
        bind_full_etc=args.bind_full_etc or cfg.defaults.get("bind_full_etc", False),
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
