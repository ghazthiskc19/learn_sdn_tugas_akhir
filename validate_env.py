#!/usr/bin/env python3
"""
validate_env.py — SDN Environment Validator
============================================
Cek semua dependency (Python package & system tools) yang dibutuhkan
untuk menjalankan eksperimen SDN dengan Mininet, OSKen, dan visualisasi.

Cara menjalankan (dari root repo):
  python3 validate_env.py
  python3 validate_env.py --no-color     # nonaktifkan warna ANSI

Exit code:
  0  — semua dependency tersedia
  1  — ada dependency yang hilang
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from typing import NamedTuple

# ─────────────────────────────────────────────────────────────────────────────
# ANSI Color Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _supports_color() -> bool:
    """Deteksi apakah terminal mendukung warna ANSI."""
    # Paksa aktif / nonaktif via env var (untuk CI/CD)
    force = os.environ.get("FORCE_COLOR", "").strip()
    if force in ("1", "true", "yes"):
        return True
    no_color = os.environ.get("NO_COLOR", "").strip()
    if no_color:
        return False
    # Cek apakah stdout adalah TTY
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


# Akan di-set oleh argparse setelah parsing; default ke auto-detect
_COLOR_ENABLED: bool = _supports_color()


def _ansi(text: str, *codes: int) -> str:
    if not _COLOR_ENABLED:
        return text
    prefix = "\033[" + ";".join(str(c) for c in codes) + "m"
    return f"{prefix}{text}\033[0m"


def green(t: str) -> str:
    return _ansi(t, 32)


def red(t: str) -> str:
    return _ansi(t, 31)


def yellow(t: str) -> str:
    return _ansi(t, 33)


def cyan(t: str) -> str:
    return _ansi(t, 36)


def bold(t: str) -> str:
    return _ansi(t, 1)


def dim(t: str) -> str:
    return _ansi(t, 2)


def italic(t: str) -> str:
    return _ansi(t, 3)


OK_TAG = lambda: green(bold(" ✓ OK   "))
FAIL_TAG = lambda: red(bold("✗ FAILED"))
SKIP_TAG = lambda: yellow(bold(" ~ SKIP "))


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────


class CheckResult(NamedTuple):
    """Hasil pengecekan satu dependency."""

    name: str  # Nama tampilan (misal "os-ken", "iperf3")
    ok: bool  # True = tersedia
    version: str | None  # String versi jika bisa diambil
    detail: str | None  # Path / pesan error tambahan
    optional: bool = False  # True = bonus check, tidak masuk hitungan gagal


# ─────────────────────────────────────────────────────────────────────────────
# Python Package Definitions
# ─────────────────────────────────────────────────────────────────────────────

# Format: import_name → (label_tampil, pip_package_name, optional)
_PYTHON_PKGS: list[tuple[str, str, str, bool]] = [
    # (import_name,  label,         pip_name,       optional)
    ("os_ken", "os-ken", "os-ken", False),
    ("pandas", "pandas", "pandas", False),
    ("matplotlib", "matplotlib", "matplotlib", False),
    ("seaborn", "seaborn", "seaborn", False),
    # ── Bonus checks (tidak wajib, tidak masuk exit code) ──────────────────
    ("mininet", "mininet", "(from source)", True),
    ("numpy", "numpy", "numpy", True),
    ("pytest", "pytest", "pytest", True),
]


def _get_py_version(mod_name: str, mod: object) -> str | None:
    """Ambil versi modul Python dari atribut standar."""
    for attr in ("__version__", "VERSION", "version"):
        val = getattr(mod, attr, None)
        if isinstance(val, str) and val:
            return val
        if isinstance(val, tuple):
            return ".".join(str(x) for x in val)
    # Fallback: coba importlib.metadata
    try:
        import importlib.metadata

        # pip package name bisa berbeda (os_ken → os-ken)
        pip_name = mod_name.replace("_", "-")
        return importlib.metadata.version(pip_name)
    except Exception:
        pass
    return None


def check_python_package(
    import_name: str,
    label: str,
    optional: bool,
) -> CheckResult:
    """Coba import satu Python package dan kembalikan CheckResult."""
    try:
        mod = __import__(import_name)
        version = _get_py_version(import_name, mod)
        return CheckResult(label, True, version, None, optional)
    except ImportError as exc:
        return CheckResult(label, False, None, str(exc), optional)
    except Exception as exc:
        return CheckResult(label, False, None, f"Error saat import: {exc}", optional)


# ─────────────────────────────────────────────────────────────────────────────
# System Tool Definitions
# ─────────────────────────────────────────────────────────────────────────────

# Format: (cmd, label, apt_package, version_flags, optional)
_SYSTEM_TOOLS: list[tuple[str, str, str, list[str], bool]] = [
    # ── Wajib ─────────────────────────────────────────────────────────────────
    ("mn", "mn (Mininet CLI)", "mininet", ["--version"], False),
    ("iperf3", "iperf3", "iperf3", ["--version"], False),
    ("ovs-ofctl", "ovs-ofctl (OVS)", "openvswitch-switch", ["--version"], False),
    ("ping", "ping", "iputils-ping", ["-V", "--version"], False),
    # ── Bonus checks ──────────────────────────────────────────────────────────
    ("ovs-vsctl", "ovs-vsctl (OVS)", "openvswitch-switch", ["--version"], True),
    ("traceroute", "traceroute", "traceroute", ["--version", "-V"], True),
    ("python3", "python3", "python3", ["--version"], True),
]


def _run_version(cmd: str, flags: list[str]) -> str | None:
    """Jalankan `cmd <flag>` dan kembalikan baris pertama output-nya."""
    for flag in flags:
        try:
            result = subprocess.run(
                [cmd, flag],
                capture_output=True,
                text=True,
                timeout=4,
            )
            raw = (result.stdout or result.stderr or "").strip()
            if raw:
                # Ambil baris pertama yang tidak kosong
                for line in raw.splitlines():
                    line = line.strip()
                    if line:
                        return line
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
    return None


def check_system_tool(
    cmd: str,
    label: str,
    version_flags: list[str],
    optional: bool,
) -> CheckResult:
    """Cek apakah command tersedia di PATH dan ambil versinya."""
    path = shutil.which(cmd)
    if path is None:
        return CheckResult(
            label, False, None, f"'{cmd}' tidak ditemukan di PATH", optional
        )
    version = _run_version(cmd, version_flags)
    return CheckResult(label, True, version, path, optional)


# ─────────────────────────────────────────────────────────────────────────────
# Display Helpers
# ─────────────────────────────────────────────────────────────────────────────

_W = 68  # lebar total baris


def _hline(char: str = "─") -> None:
    print("  " + char * (_W - 2))


def _status_row(result: CheckResult) -> None:
    """Cetak satu baris status: [nama] [OK/FAIL] [versi/detail]"""
    LABEL_W = 26

    opt_marker = italic(dim(" (opt)")) if result.optional else "      "
    label = f"{result.name:<{LABEL_W}}{opt_marker}"

    if result.ok:
        tag = OK_TAG()
        version = dim(f"  {result.version}") if result.version else ""
        print(f"  {label}  {tag}{version}")
    else:
        tag = FAIL_TAG()
        detail = (
            dim(f"\n  {'':>{LABEL_W + 10}}→ {result.detail}") if result.detail else ""
        )
        print(f"  {label}  {tag}{detail}")


def _section_header(title: str, icon: str = "▸") -> None:
    print(f"\n  {bold(cyan(icon + '  ' + title))}")
    _hline()


# ─────────────────────────────────────────────────────────────────────────────
# Install Instruction Builder
# ─────────────────────────────────────────────────────────────────────────────


def _build_pip_cmd(missing: list[tuple[str, str]]) -> str | None:
    """Buat satu perintah pip install dari daftar (label, pip_name) yang hilang."""
    names = [pip_name for _label, pip_name in missing if not pip_name.startswith("(")]
    if not names:
        return None
    return "pip install " + " ".join(names)


def _build_apt_cmd(missing: list[tuple[str, str]]) -> str | None:
    """Buat satu perintah apt install dari daftar (label, apt_pkg) yang hilang."""
    # Deduplikasi (ovs-ofctl & ovs-vsctl keduanya pakai openvswitch-switch)
    seen: set[str] = set()
    pkgs: list[str] = []
    for _label, apt_pkg in missing:
        if apt_pkg not in seen:
            seen.add(apt_pkg)
            pkgs.append(apt_pkg)
    if not pkgs:
        return None
    return "sudo apt install " + " ".join(pkgs)


# ─────────────────────────────────────────────────────────────────────────────
# Main Validator
# ─────────────────────────────────────────────────────────────────────────────


def run_validation() -> bool:
    """
    Jalankan semua pengecekan, cetak laporan, kembalikan True jika semua
    dependency *wajib* tersedia (optional tidak diperhitungkan).
    """

    # ── 0. Header ─────────────────────────────────────────────────────────────
    print()
    print("  " + bold("═" * (_W - 2)))
    print("  " + bold(cyan("   SDN Environment Validator")))
    print("  " + bold(f"   Python {sys.version.split()[0]}  ·  {sys.executable}"))
    print("  " + bold("═" * (_W - 2)))

    # ── 1. Python Packages ────────────────────────────────────────────────────
    _section_header("Python Packages", "🐍")

    py_results: list[CheckResult] = []
    for import_name, label, _pip_name, optional in _PYTHON_PKGS:
        r = check_python_package(import_name, label, optional)
        py_results.append(r)
        _status_row(r)

    # ── 2. System Tools ───────────────────────────────────────────────────────
    _section_header("System Tools  (CLI / Network)", "🛠")

    sys_results: list[CheckResult] = []
    for cmd, label, _apt_pkg, version_flags, optional in _SYSTEM_TOOLS:
        r = check_system_tool(cmd, label, version_flags, optional)
        sys_results.append(r)
        _status_row(r)

    # ── 3. Kumpulkan yang Hilang ──────────────────────────────────────────────
    missing_py: list[tuple[str, str]] = []  # (label, pip_name)
    for r, (_imp, label, pip_name, optional) in zip(py_results, _PYTHON_PKGS):
        if not r.ok and not optional:
            missing_py.append((label, pip_name))

    missing_sys: list[tuple[str, str]] = []  # (label, apt_pkg)
    for r, (cmd, label, apt_pkg, _flags, optional) in zip(sys_results, _SYSTEM_TOOLS):
        if not r.ok and not optional:
            missing_sys.append((label, apt_pkg))

    all_ok = not missing_py and not missing_sys

    # ── 4. Summary ────────────────────────────────────────────────────────────
    print()
    print("  " + bold("═" * (_W - 2)))
    print("  " + bold(cyan("   Ringkasan Validasi")))
    _hline("─")

    # Hitung statistik
    total_req_py = sum(1 for *_, opt in _PYTHON_PKGS if not opt)
    total_req_sys = sum(1 for *_, opt in _SYSTEM_TOOLS if not opt)
    pass_py = total_req_py - len(missing_py)
    pass_sys = total_req_sys - len(missing_sys)

    print(
        f"\n  {'Python packages':30}  {green(str(pass_py)) + dim(f'/{total_req_py}')} tersedia"
    )
    print(
        f"  {'System tools':30}  {green(str(pass_sys)) + dim(f'/{total_req_sys}')} tersedia"
    )
    print()

    if all_ok:
        # ── Sukses ────────────────────────────────────────────────────────────
        print(
            "  "
            + green(bold("✅  Environment valid! Anda siap menjalankan eksperimen."))
        )
        print()
        print(dim("  Perintah berikutnya yang bisa dijalankan:"))
        print(dim("    python3 SPF/dijkstra_osken_controller.py --verbose"))
        print(dim("    python3 scripts/visualize/visualize.py --demo"))
        print(dim("    python3 -m pytest SPF/tests/ -v"))

    else:
        # ── Ada yang Kurang ───────────────────────────────────────────────────
        print("  " + red(bold("❌  Beberapa dependency belum terinstal.")))
        print()

        if missing_py:
            print("  " + bold(yellow("⚠  Python packages yang kurang:")))
            for label, pip_name in missing_py:
                marker = (
                    dim("(install dari source)") if pip_name.startswith("(") else ""
                )
                print(f"     {red('✗')} {label} {marker}")
            pip_cmd = _build_pip_cmd(missing_py)
            if pip_cmd:
                print()
                print("  " + bold("  Instal dengan:"))
                print(f"    {cyan(pip_cmd)}")
            print()

        if missing_sys:
            print("  " + bold(yellow("⚠  System tools yang kurang:")))
            for label, apt_pkg in missing_sys:
                print(f"     {red('✗')} {label}  {dim('→ apt: ' + apt_pkg)}")
            apt_cmd = _build_apt_cmd(missing_sys)
            if apt_cmd:
                print()
                print("  " + bold("  Instal dengan:"))
                print(f"    {cyan(apt_cmd)}")
            print()

        # Tips Mininet (sering diinstal dari source, bukan apt)
        mn_missing = any(
            cmd == "mn"
            for (cmd, *_, opt) in _SYSTEM_TOOLS
            if not opt and shutil.which(cmd) is None
        )
        if mn_missing:
            print(
                "  "
                + dim("  Catatan Mininet: Jika apt tidak tersedia, instal dari source:")
            )
            print("  " + dim("    git clone https://github.com/mininet/mininet.git"))
            print(
                "  "
                + dim("    cd mininet && sudo PYTHON=python3 ./util/install.sh -nfv")
            )
            print()

    print("  " + bold("═" * (_W - 2)))
    print()

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    global _COLOR_ENABLED

    parser = argparse.ArgumentParser(
        prog="validate_env.py",
        description="Validasi environment untuk proyek SDN (Mininet + OSKen + Visualisasi)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Contoh:\n  python3 validate_env.py\n  python3 validate_env.py --no-color\n"
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Nonaktifkan warna ANSI (berguna untuk output log/CI).",
    )
    args = parser.parse_args()

    if args.no_color:
        _COLOR_ENABLED = False

    all_ok = run_validation()
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
