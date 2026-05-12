#!/usr/bin/env python3
"""
visualize.py — Visualisasi Interaktif Hasil Eksperimen SDN
===========================================================

Lokasi script : scripts/visualize/visualize.py
Output grafik : visualize/{topology}/{metric}/   (relatif terhadap root repo)

Cara menjalankan (dari root repo):
  python3 scripts/visualize/visualize.py
  python3 scripts/visualize/visualize.py --demo     # buat data sampel sintetis dulu

Format CSV yang didukung (output experiment scripts):
  results/{topology}/convergence/  → Scenario, Convergence_Time_Seconds, Status
  results/{topology}/latency/      → scenario, jitter_ms, first_packet_ms, rtt_avg_ms, ...
  results/{topology}/throughput/   → scenario, throughput_mbps, retransmits, ...
  results/{topology}/hopcount/     → test, hop_count

Setiap kolom numerik menjadi satu "Metric" di DataFrame gabungan long-format:
  Algorithm | Scenario | Metric | Value
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import random
import sys

import matplotlib

# Gunakan backend Agg (non-GUI) → cocok untuk container / server tanpa display
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# ─────────────────────────────────────────────────────────────────────────────
# Paths — dihitung relatif terhadap lokasi script ini
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # 2 level ke atas → learn_sdn/
RESULTS_BASE = os.path.join(REPO_ROOT, "scripts", "experiments", "results")
OUTPUT_BASE = os.path.join(REPO_ROOT, "visualize")

# ─────────────────────────────────────────────────────────────────────────────
# Menu Options
# ─────────────────────────────────────────────────────────────────────────────

# Format: { key: (label_tampil, value_internal) }
TOPOLOGY_OPTIONS: dict[str, tuple[str, str]] = {
    "1": ("Mesh", "mesh"),
    "2": ("Hierarchical", "hierarchy"),
}

CHART_OPTIONS: dict[str, tuple[str, str]] = {
    "1": ("Grouped Bar Chart", "bar"),
    "2": ("Boxplot", "box"),
    "3": ("Line Plot", "line"),
    "4": ("Violin Plot", "violin"),
    "5": ("Point Plot / Scatter", "point"),
}

# ─────────────────────────────────────────────────────────────────────────────
# Seaborn Version Detection
# ─────────────────────────────────────────────────────────────────────────────

# Seaborn >= 0.12 mengganti parameter `ci` dengan `errorbar`
_SNS_VERSION: tuple[int, ...] = tuple(int(x) for x in sns.__version__.split(".")[:2])
_SNS_NEW: bool = _SNS_VERSION >= (0, 12)

# Palet warna profesional untuk laporan
PALETTE = "Set2"

# ─────────────────────────────────────────────────────────────────────────────
# Demo Data Generator
# ─────────────────────────────────────────────────────────────────────────────

DEMO_ALGORITHMS = ["dijkstra", "astar", "bfs", "bellman_ford", "floyd_warshall"]
DEMO_SEED = 42


def generate_demo_data(topology_key: str) -> None:
    """
    Buat CSV sintetis di dalam results/{topology_key}/ untuk semua metric folder.

    Data bersifat deterministik (reproducible) berkat random.Random(DEMO_SEED).
    CSV yang dihasilkan mengikuti skema persis sama dengan experiment scripts asli.
    """
    rng = random.Random(DEMO_SEED)
    base = os.path.join(RESULTS_BASE, topology_key)

    print(f"\n{'─' * 60}")
    print(f"  [Demo] Membuat data sampel untuk topologi: '{topology_key}'")
    print(f"  Target folder: {os.path.relpath(base, REPO_ROOT)}/")
    print(f"{'─' * 60}")

    # ── Convergence ──────────────────────────────────────────────────────────
    # Schema: Scenario, Convergence_Time_Seconds, Status
    conv_dir = os.path.join(base, "convergence")
    os.makedirs(conv_dir, exist_ok=True)
    conv_scenarios = [
        "Cold-Start Convergence",
        "Core Failure",
        "Edge Failure",
        "Node Failure",
    ]
    for algo in DEMO_ALGORITHMS:
        path = os.path.join(conv_dir, f"{algo}_convergence_0.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Scenario", "Convergence_Time_Seconds", "Status"])
            for scn in conv_scenarios:
                # Algoritma yang lebih cepat dapat nilai lebih kecil
                base_val = rng.uniform(0.3, 3.5)
                w.writerow([scn, f"{base_val:.3f}", "SUCCESS"])
    print(f"  ✓ convergence/ — {len(DEMO_ALGORITHMS)} file CSV")

    # ── Latency ───────────────────────────────────────────────────────────────
    # Schema: scenario, jitter_ms, first_packet_ms, subsequent_avg_ms, rtt_avg_ms
    lat_dir = os.path.join(base, "latency")
    os.makedirs(lat_dir, exist_ok=True)
    lat_scenarios = [
        "udp_jitter_loss",
        "first_vs_subsequent",
        "congestion",
        "convergence_latency_spike",
    ]
    for algo in DEMO_ALGORITHMS:
        path = os.path.join(lat_dir, f"{algo}_latency_0.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "scenario",
                    "jitter_ms",
                    "first_packet_ms",
                    "subsequent_avg_ms",
                    "rtt_avg_ms",
                ]
            )
            for scn in lat_scenarios:
                jitter = round(rng.uniform(0.05, 6.0), 3)
                first = round(rng.uniform(30.0, 280.0), 3)
                subseq = round(rng.uniform(1.5, 35.0), 3)
                rtt = round(rng.uniform(2.0, 60.0), 3)
                w.writerow([scn, jitter, first, subseq, rtt])
    print(f"  ✓ latency/     — {len(DEMO_ALGORITHMS)} file CSV")

    # ── Throughput ────────────────────────────────────────────────────────────
    # Schema: scenario, throughput_mbps, retransmits
    thr_dir = os.path.join(base, "throughput")
    os.makedirs(thr_dir, exist_ok=True)
    thr_scenarios = ["baseline", "multiflow", "failover", "mss_compare"]
    for algo in DEMO_ALGORITHMS:
        path = os.path.join(thr_dir, f"{algo}_throughput_0.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["scenario", "throughput_mbps", "retransmits"])
            for scn in thr_scenarios:
                thr = round(rng.uniform(35.0, 950.0), 2)
                retr = int(rng.uniform(0, 60))
                w.writerow([scn, thr, retr])
    print(f"  ✓ throughput/  — {len(DEMO_ALGORITHMS)} file CSV")

    # ── Hop Count ─────────────────────────────────────────────────────────────
    # Schema: test, hop_count
    hop_dir = os.path.join(base, "hopcount")
    os.makedirs(hop_dir, exist_ok=True)
    hop_scenarios = [
        "progressive_h1_h2",
        "progressive_h1_h5",
        "reroute_baseline",
        "reroute_core_failure",
    ]
    for algo in DEMO_ALGORITHMS:
        path = os.path.join(hop_dir, f"{algo}_hopcount_0.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["test", "hop_count"])
            for scn in hop_scenarios:
                hops = int(rng.uniform(2, 8))
                w.writerow([scn, hops])
    print(f"  ✓ hopcount/    — {len(DEMO_ALGORITHMS)} file CSV")

    total = len(DEMO_ALGORITHMS) * 4
    print(f"\n  ✓ Selesai! {total} file CSV dibuat di:")
    print(f"    {os.path.relpath(base, REPO_ROOT)}/")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Data Loading & Normalisation
# ─────────────────────────────────────────────────────────────────────────────

# Kolom pengenal baris (bukan nilai numerik metrik).
# Lowercase karena pengecekan dilakukan dengan col.lower().
_NON_METRIC_COLS: frozenset[str] = frozenset(
    {
        "algorithm",
        "scenario",
        "status",
        "error",
        "test",
        "phase",
        "src",
        "dst",
        "path",
        "transfer",  # string "10 MBytes" dari throughput
        "bitrate",  # string "95 Mbits/sec" dari throughput
    }
)


def _extract_algo(csv_path: str) -> str:
    """
    Ekstrak nama algoritma dari nama file dengan pola <algo>_<metric>_<idx>.csv

    Contoh:
      dijkstra_latency_0.csv         → "dijkstra"
      bellman_ford_convergence_0.csv → "bellman_ford"
      astar_hopcount_1.csv           → "astar"
      floyd_warshall_throughput_0.csv → "floyd_warshall"
    """
    name = os.path.splitext(os.path.basename(csv_path))[0]
    parts = name.split("_")
    known_metrics = {"convergence", "latency", "throughput", "hopcount"}

    for i, part in enumerate(parts):
        if part in known_metrics:
            algo = "_".join(parts[:i])
            return algo if algo else "unknown"

    # Fallback: jika bagian terakhir adalah digit, dua bagian akhir = metric_idx
    if len(parts) >= 3 and parts[-1].isdigit():
        return "_".join(parts[:-2])

    return parts[0] if parts else "unknown"


def _find_scenario_col(df: pd.DataFrame) -> str | None:
    """Kembalikan nama kolom skenario yang pertama ditemukan."""
    for candidate in ("Scenario", "scenario", "test", "phase"):
        if candidate in df.columns:
            return candidate
    return None


def _load_one_csv(csv_path: str) -> pd.DataFrame:
    """
    Muat satu file CSV dan normalkan menjadi format panjang (long format):

      Algorithm | Scenario | Metric | Value

    Kolom numerik pada CSV asli menjadi baris-baris 'Metric'/'Value'.
    Kolom string (status, error, transfer, bitrate) dilewati otomatis.
    """
    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        raise ValueError(f"Gagal membaca CSV: {exc}") from exc

    if df.empty:
        return pd.DataFrame()

    # ── Tambahkan kolom Algorithm (dari nama file) ────────────────────────────
    df["Algorithm"] = _extract_algo(csv_path)

    # ── Normalkan kolom Scenario ──────────────────────────────────────────────
    scn_col = _find_scenario_col(df)
    if scn_col is None:
        df["Scenario"] = "default"
    elif scn_col != "Scenario":
        df = df.rename(columns={scn_col: "Scenario"})

    # ── Temukan kolom yang mengandung nilai numerik ───────────────────────────
    reserved = {"Algorithm", "Scenario"}
    value_cols: list[str] = []

    for col in df.columns:
        if col in reserved or col.lower() in _NON_METRIC_COLS:
            continue
        numeric_series = pd.to_numeric(df[col], errors="coerce")
        if numeric_series.notna().any():
            df[col] = numeric_series  # konversi in-place
            value_cols.append(col)

    if not value_cols:
        return pd.DataFrame()

    # ── Melt → long format ────────────────────────────────────────────────────
    melted = df[["Algorithm", "Scenario"] + value_cols].melt(
        id_vars=["Algorithm", "Scenario"],
        value_vars=value_cols,
        var_name="Metric",
        value_name="Value",
    )
    melted["Value"] = pd.to_numeric(melted["Value"], errors="coerce")
    melted = melted.dropna(subset=["Value"]).reset_index(drop=True)

    return melted


def build_dataframe(topology_key: str) -> pd.DataFrame:
    """
    Pindai semua subfolder metric dalam results/{topology_key}/
    dan kembalikan DataFrame gabungan ber-kolom:

      Algorithm | Scenario | Metric | Value

    Raises:
      FileNotFoundError  — jika folder topologi tidak ada
    """
    topo_path = os.path.join(RESULTS_BASE, topology_key)

    if not os.path.isdir(topo_path):
        raise FileNotFoundError(
            f"Folder topologi tidak ditemukan:\n"
            f"  {topo_path}\n\n"
            f"Pastikan hasil eksperimen sudah ada, atau jalankan dengan:\n"
            f"  python3 scripts/visualize/visualize.py --demo"
        )

    # Cari semua CSV secara rekursif, abaikan file tersembunyi & .gitkeep
    csv_files = sorted(
        glob.glob(os.path.join(topo_path, "**", "*.csv"), recursive=True)
    )
    csv_files = [
        f
        for f in csv_files
        if not os.path.basename(f).startswith(".")
        and not os.path.basename(f).endswith(".gitkeep")
    ]

    if not csv_files:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    skipped = 0

    for csv_file in csv_files:
        try:
            frame = _load_one_csv(csv_file)
            if not frame.empty:
                frames.append(frame)
        except Exception as exc:
            skipped += 1
            print(f"  [⚠] Lewati {os.path.basename(csv_file)}: {exc}")

    if skipped:
        print(f"  [Info] {skipped} file CSV dilewati karena error atau kosong.")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates()
    return combined


# ─────────────────────────────────────────────────────────────────────────────
# Plotting
# ─────────────────────────────────────────────────────────────────────────────


def _seaborn_barplot(
    ax: plt.Axes, data: pd.DataFrame, x: str, y: str, hue: str, palette: str
) -> None:
    """Grouped bar chart dengan error bar ±SD. Kompatibel seaborn < 0.12 dan >= 0.12."""
    kw: dict = dict(data=data, x=x, y=y, hue=hue, palette=palette, ax=ax, capsize=0.05)
    if _SNS_NEW:
        kw["errorbar"] = "sd"
    else:
        kw["ci"] = "sd"
    sns.barplot(**kw)


def _seaborn_lineplot(
    ax: plt.Axes, data: pd.DataFrame, x: str, y: str, hue: str, palette: str
) -> None:
    """Line plot. Kompatibel seaborn < 0.12 dan >= 0.12."""
    kw: dict = dict(
        data=data, x=x, y=y, hue=hue, palette=palette, ax=ax, markers=True, dashes=False
    )
    if _SNS_NEW:
        kw["errorbar"] = None
    else:
        kw["ci"] = None
    sns.lineplot(**kw)


def _seaborn_pointplot(
    ax: plt.Axes, data: pd.DataFrame, x: str, y: str, hue: str, palette: str
) -> None:
    """Point plot / scatter. Fallback ke scatterplot jika gagal."""
    kw: dict = dict(data=data, x=x, y=y, hue=hue, palette=palette, ax=ax, dodge=True)
    if _SNS_NEW:
        kw["errorbar"] = None
    else:
        kw["ci"] = None
    try:
        sns.pointplot(**kw)
    except TypeError:
        # Jika ada parameter yang tidak kompatibel, coba tanpa dodge
        kw.pop("dodge", None)
        try:
            sns.pointplot(**kw)
        except Exception:
            # Final fallback ke scatter
            sns.scatterplot(
                data=data, x=x, y=y, hue=hue, palette=palette, ax=ax, s=80, alpha=0.8
            )


def _seaborn_violinplot(
    ax: plt.Axes, data: pd.DataFrame, x: str, y: str, hue: str, palette: str
) -> None:
    """Violin plot. Fallback ke boxplot jika data terlalu sedikit untuk KDE."""
    try:
        sns.violinplot(data=data, x=x, y=y, hue=hue, palette=palette, ax=ax)
    except Exception as exc:
        print(f"  [Info] Violin plot gagal ({exc}) → fallback ke boxplot.")
        sns.boxplot(data=data, x=x, y=y, hue=hue, palette=palette, ax=ax)


def make_plot(
    df: pd.DataFrame,
    metric: str,
    chart_type: str,
    chart_label: str,
    topo_label: str,
    topo_key: str,
) -> None:
    """
    Filter DataFrame berdasarkan 'metric', buat grafik seaborn yang dipilih,
    dan simpan sebagai PNG DPI-300 ke:
      visualize/{topo_key}/{metric}/{prefix}_{metric}.png
    """
    # ── 1. Filter data ────────────────────────────────────────────────────────
    plot_df = df[df["Metric"] == metric].copy()

    if plot_df.empty:
        print(f"\n  [Error] Tidak ada data untuk metrik '{metric}'.")
        return

    # Urutkan algoritma agar konsisten di semua grafik
    plot_df = plot_df.sort_values("Algorithm")

    # ── 2. Buat folder output ─────────────────────────────────────────────────
    out_dir = os.path.join(OUTPUT_BASE, topo_key, metric)
    os.makedirs(out_dir, exist_ok=True)

    prefix_map = {
        "bar": "bar_chart",
        "box": "boxplot",
        "line": "line_plot",
        "violin": "violin_plot",
        "point": "point_plot",
    }
    filename = f"{prefix_map[chart_type]}_{metric}.png"
    out_path = os.path.join(out_dir, filename)

    # ── 3. Buat figure ────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(13, 6))

    try:
        if chart_type == "bar":
            _seaborn_barplot(ax, plot_df, "Algorithm", "Value", "Scenario", PALETTE)

        elif chart_type == "box":
            sns.boxplot(
                data=plot_df,
                x="Algorithm",
                y="Value",
                hue="Scenario",
                palette=PALETTE,
                ax=ax,
            )

        elif chart_type == "line":
            _seaborn_lineplot(ax, plot_df, "Algorithm", "Value", "Scenario", PALETTE)

        elif chart_type == "violin":
            _seaborn_violinplot(ax, plot_df, "Algorithm", "Value", "Scenario", PALETTE)

        elif chart_type == "point":
            _seaborn_pointplot(ax, plot_df, "Algorithm", "Value", "Scenario", PALETTE)

    except Exception as exc:
        print(f"\n  [Error] Gagal membuat {chart_label}: {exc}")
        plt.close(fig)
        return

    # ── 4. Styling ─────────────────────────────────────────────────────────────
    title = (
        f"{metric.replace('_', ' ').title()}"
        f"  ·  {topo_label} Topology"
        f"  ·  {chart_label}"
    )
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Algorithm", fontsize=11, labelpad=8)
    ax.set_ylabel(metric.replace("_", " ").title(), fontsize=11, labelpad=8)
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Pindahkan legend ke luar area grafik
    legend = ax.get_legend()
    if legend is not None:
        ax.legend(
            title="Scenario",
            bbox_to_anchor=(1.01, 1),
            loc="upper left",
            borderaxespad=0,
            framealpha=0.9,
        )

    # ── 5. Simpan ─────────────────────────────────────────────────────────────
    plt.tight_layout()
    try:
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        rel_path = os.path.relpath(out_path, REPO_ROOT)
        print(f"\n  ✓ Grafik disimpan  →  {rel_path}")
        print(f"     Metrik   : {metric}")
        print(f"     Topologi : {topo_label}")
        print(f"     Grafik   : {chart_label}")
        print(
            f"     Baris    : {len(plot_df)}  |  "
            f"Algoritma: {plot_df['Algorithm'].nunique()}  |  "
            f"Skenario : {plot_df['Scenario'].nunique()}"
        )
    except Exception as exc:
        print(f"\n  [Error] Gagal menyimpan file: {exc}")
    finally:
        plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Interactive CLI Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _sep(char: str = "─", width: int = 60) -> None:
    print(char * width)


def _prompt_choice(
    heading: str,
    options: dict[str, tuple[str, str]],
) -> tuple[str, str, str]:
    """
    Tampilkan menu bernomor dan tunggu input user.

    Returns:
      (key, label, value)  — tuple tiga elemen dari pilihan user
      Ketik 'q' untuk keluar dari program.
    """
    while True:
        print(f"\n{heading}")
        for key, (label, _value) in options.items():
            print(f"  {key}. {label}")
        print("  q. Keluar")

        raw = input("\n  Pilihan Anda: ").strip().lower()

        if raw == "q":
            print("\n  Keluar dari program.")
            sys.exit(0)

        if raw in options:
            label, value = options[raw]
            return raw, label, value

        print(f"  [!] Input tidak valid: '{raw}'. Silakan pilih dari daftar di atas.\n")


def _prompt_metric(metrics: list[str]) -> str:
    """
    Tampilkan daftar metrik yang ada di DataFrame dan kembalikan pilihan user.
    Ketik nomor sesuai daftar, atau 'q' untuk keluar.
    """
    print("\n  Metrik yang tersedia (dari kolom 'Metric'):")
    print()
    for i, m in enumerate(metrics, 1):
        print(f"  {i:>3}. {m}")
    print()
    print("    q. Keluar")

    while True:
        raw = input("\n  Pilih nomor metrik: ").strip().lower()

        if raw == "q":
            print("\n  Keluar dari program.")
            sys.exit(0)

        try:
            idx = int(raw) - 1
            if 0 <= idx < len(metrics):
                return metrics[idx]
        except ValueError:
            pass

        print(f"  [!] Input tidak valid. Masukkan angka 1–{len(metrics)}.\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    # ── Argparse ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        prog="visualize.py",
        description="Visualisasi Interaktif Hasil Eksperimen SDN (Mesh & Hierarchical)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Contoh:\n"
            "  python3 scripts/visualize/visualize.py\n"
            "  python3 scripts/visualize/visualize.py --demo\n"
        ),
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Buat data sampel CSV sintetis sebelum memulai visualisasi.",
    )
    args = parser.parse_args()

    # ── Header ────────────────────────────────────────────────────────────────
    _sep("═")
    print("  SDN Experiment Results — Interactive Visualizer")
    print(f"  seaborn {sns.__version__}  |  pandas {pd.__version__}")
    print()
    print(f"  Repo root  :  {REPO_ROOT}")
    print(f"  Results    :  {os.path.relpath(RESULTS_BASE, REPO_ROOT)}/")
    print(f"  Output     :  visualize/{{topology}}/{{metric}}/")
    _sep("═")

    # ── [0] Mode Demo ─────────────────────────────────────────────────────────
    if args.demo:
        print("\n[Mode Demo] Pilih topologi untuk data sampel yang akan dibuat:")
        _, topo_label_demo, topo_key_demo = _prompt_choice(
            "Pilih Topologi:", TOPOLOGY_OPTIONS
        )
        generate_demo_data(topo_key_demo)
        print(f"  Data sampel untuk '{topo_label_demo}' sudah siap.")
        print("  Lanjutkan ke visualisasi...\n")

    # ── Loop Utama ────────────────────────────────────────────────────────────
    while True:
        # ── [1/3] Pilih Topologi ──────────────────────────────────────────────
        _, topo_label, topo_key = _prompt_choice(
            "[1/3]  Pilih Topologi:", TOPOLOGY_OPTIONS
        )
        print(f"\n  ✓ Topologi dipilih: {topo_label} ({topo_key})")

        # ── Muat & Gabungkan CSV ──────────────────────────────────────────────
        results_rel = os.path.relpath(os.path.join(RESULTS_BASE, topo_key), REPO_ROOT)
        print(f"\n  Memuat CSV dari: {results_rel}/...")

        try:
            df = build_dataframe(topo_key)
        except FileNotFoundError as exc:
            print(f"\n  [Error] {exc}")
            _sep()
            input("  Tekan Enter untuk kembali ke menu...")
            continue

        if df.empty:
            print(
                f"\n  [Error] Tidak ada data CSV valid untuk topologi '{topo_label}'.\n"
                f"\n  Solusi:\n"
                f"    1. Jalankan eksperimen terlebih dahulu:\n"
                f"       python3 scripts/experiment_system/run_experiment.py\n"
                f"    2. Atau gunakan data sampel:\n"
                f"       python3 scripts/visualize/visualize.py --demo\n"
            )
            _sep()
            input("  Tekan Enter untuk kembali ke menu...")
            continue

        metrics = sorted(df["Metric"].unique().tolist())
        n_algo = df["Algorithm"].nunique()
        n_rows = len(df)
        n_scn = df["Scenario"].nunique()

        print(
            f"  ✓ Data dimuat: {n_rows} baris  |  {len(metrics)} metrik  |  "
            f"{n_algo} algoritma  |  {n_scn} skenario"
        )

        # ── [2/3] Pilih Metrik ────────────────────────────────────────────────
        print("\n[2/3]  Pilih Metrik:")
        metric = _prompt_metric(metrics)
        count = int((df["Metric"] == metric).sum())
        print(f"\n  ✓ Metrik dipilih: '{metric}'  ({count} baris data)")

        # ── [3/3] Pilih Jenis Grafik ──────────────────────────────────────────
        _, chart_label, chart_type = _prompt_choice(
            "[3/3]  Pilih Jenis Grafik:", CHART_OPTIONS
        )
        print(f"\n  ✓ Grafik: {chart_label}")

        # ── Buat & Simpan Grafik ──────────────────────────────────────────────
        _sep()
        print(f"  Membuat {chart_label}...")

        make_plot(df, metric, chart_type, chart_label, topo_label, topo_key)

        # ── Lanjut? ───────────────────────────────────────────────────────────
        _sep()
        while True:
            repeat = input("  Buat grafik lain? (y/n): ").strip().lower()
            if repeat in ("y", "n"):
                break
            print("  [!] Ketik 'y' untuk ya, 'n' untuk tidak.\n")

        if repeat == "n":
            _sep("═")
            print("  Terima kasih! Program selesai.")
            _sep("═")
            break

        print()  # spasi sebelum iterasi berikutnya


if __name__ == "__main__":
    main()
