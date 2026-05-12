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


def _build_hue_kw(hue: str | None, palette: str) -> dict:
    """
    Kembalikan dict keyword untuk parameter hue & palette seaborn.
    Jika hue=None, kembalikan dict kosong agar seaborn pakai warna default —
    mencegah FutureWarning 'palette without hue'.
    """
    if hue is not None:
        return {"hue": hue, "palette": palette}
    return {}


def _seaborn_barplot(
    ax: plt.Axes, data: pd.DataFrame, x: str, y: str, hue: str | None, palette: str
) -> None:
    """Grouped bar chart dengan error bar ±SD. Kompatibel seaborn < 0.12 dan >= 0.12."""
    kw: dict = dict(
        data=data, x=x, y=y, ax=ax, capsize=0.05, **_build_hue_kw(hue, palette)
    )
    if _SNS_NEW:
        kw["errorbar"] = "sd"
    else:
        kw["ci"] = "sd"
    sns.barplot(**kw)


def _seaborn_lineplot(
    ax: plt.Axes, data: pd.DataFrame, x: str, y: str, hue: str | None, palette: str
) -> None:
    """Line plot. Kompatibel seaborn < 0.12 dan >= 0.12."""
    kw: dict = dict(
        data=data,
        x=x,
        y=y,
        ax=ax,
        markers=True,
        dashes=False,
        **_build_hue_kw(hue, palette),
    )
    if _SNS_NEW:
        kw["errorbar"] = None
    else:
        kw["ci"] = None
    sns.lineplot(**kw)


def _seaborn_pointplot(
    ax: plt.Axes, data: pd.DataFrame, x: str, y: str, hue: str | None, palette: str
) -> None:
    """Point plot / scatter. dodge hanya aktif saat hue ada. Fallback ke scatter jika gagal."""
    kw: dict = dict(data=data, x=x, y=y, ax=ax, **_build_hue_kw(hue, palette))
    if hue is not None:
        kw["dodge"] = True  # dodge hanya bermakna saat ada hue
    if _SNS_NEW:
        kw["errorbar"] = None
    else:
        kw["ci"] = None
    try:
        sns.pointplot(**kw)
    except TypeError:
        kw.pop("dodge", None)
        try:
            sns.pointplot(**kw)
        except Exception:
            # Final fallback ke scatterplot
            sns.scatterplot(
                data=data,
                x=x,
                y=y,
                ax=ax,
                s=80,
                alpha=0.8,
                **_build_hue_kw(hue, palette),
            )


def _seaborn_violinplot(
    ax: plt.Axes, data: pd.DataFrame, x: str, y: str, hue: str | None, palette: str
) -> None:
    """Violin plot. Fallback ke boxplot jika data terlalu sedikit untuk KDE."""
    kw = dict(data=data, x=x, y=y, ax=ax, **_build_hue_kw(hue, palette))
    try:
        sns.violinplot(**kw)
    except Exception as exc:
        print(f"  [Info] Violin plot gagal ({exc}) → fallback ke boxplot.")
        sns.boxplot(**kw)


# Prefix nama file untuk setiap jenis grafik
_CHART_PREFIX: dict[str, str] = {
    "bar": "bar_chart",
    "box": "boxplot",
    "line": "line_plot",
    "violin": "violin_plot",
    "point": "point_plot",
}


def make_plot(
    df: pd.DataFrame,
    metric: str,
    chart_type: str,
    chart_label: str,
    topo_label: str,
    topo_key: str,
    algo_filter: str | None,  # None  = semua algoritma (grafik perbandingan)
    scenario_filter: str | None,  # None  = semua skenario (gabungan)
    scenario_idx: int,  # 0=semua, 1-N=skenario tertentu (untuk nama file)
) -> None:
    """
    Filter DataFrame, pilih sumbu secara otomatis, buat grafik, dan simpan ke:
      visualize/{topo_key}/{metric}/{algo}_{metric}_{scenario_idx}_{chart_prefix}.png

    Logika sumbu:
      algo_filter=None  + scenario_filter=None  → X=Algorithm,  hue=Scenario
      algo_filter=None  + scenario_filter=<scn> → X=Algorithm,  hue=None
      algo_filter=<alg> + scenario_filter=None  → X=Scenario,   hue=None
      algo_filter=<alg> + scenario_filter=<scn> → X=Scenario,   hue=None
    """
    # ── 1. Filter data ────────────────────────────────────────────────────────
    plot_df = df[df["Metric"] == metric].copy()

    if algo_filter is not None:
        plot_df = plot_df[plot_df["Algorithm"] == algo_filter]

    if scenario_filter is not None:
        plot_df = plot_df[plot_df["Scenario"] == scenario_filter]

    if plot_df.empty:
        print(
            f"\n  [Error] Tidak ada data untuk kombinasi filter yang dipilih."
            f"\n          Metrik='{metric}', Algoritma='{algo_filter}', "
            f"Skenario='{scenario_filter}'"
        )
        return

    # ── 2. Tentukan sumbu X dan Hue secara otomatis ───────────────────────────
    # Satu algoritma terpilih → X = Scenario (lebih informatif per-algo)
    # Semua algoritma        → X = Algorithm, Hue = Scenario (perbandingan)
    if algo_filter is not None:
        x_col = "Scenario"
        hue_col = None  # single algo: warna berbeda tidak dibutuhkan
    else:
        x_col = "Algorithm"
        hue_col = "Scenario" if scenario_filter is None else None

    plot_df = plot_df.sort_values(x_col)

    # ── 3. Nama file: {algo}_{metric}_{scenario_idx}_{chart_prefix}.png ───────
    algo_part = algo_filter if algo_filter is not None else "all"
    filename = f"{algo_part}_{metric}_{scenario_idx}_{_CHART_PREFIX[chart_type]}.png"

    out_dir = os.path.join(OUTPUT_BASE, topo_key, metric)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)

    # ── 4. Buat figure ────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(13, 6))

    try:
        if chart_type == "bar":
            _seaborn_barplot(ax, plot_df, x_col, "Value", hue_col, PALETTE)

        elif chart_type == "box":
            kw = dict(
                data=plot_df,
                x=x_col,
                y="Value",
                ax=ax,
                **_build_hue_kw(hue_col, PALETTE),
            )
            sns.boxplot(**kw)

        elif chart_type == "line":
            _seaborn_lineplot(ax, plot_df, x_col, "Value", hue_col, PALETTE)

        elif chart_type == "violin":
            _seaborn_violinplot(ax, plot_df, x_col, "Value", hue_col, PALETTE)

        elif chart_type == "point":
            _seaborn_pointplot(ax, plot_df, x_col, "Value", hue_col, PALETTE)

    except Exception as exc:
        print(f"\n  [Error] Gagal membuat {chart_label}: {exc}")
        plt.close(fig)
        return

    # ── 5. Styling ─────────────────────────────────────────────────────────────
    # Judul mencantumkan algo dan skenario yang dipilih
    algo_title = algo_filter or "All Algorithms"
    scn_title = scenario_filter or "All Scenarios"
    title = (
        f"{metric.replace('_', ' ').title()}"
        f"  ·  {topo_label}"
        f"  ·  {algo_title}"
        f"  ·  {scn_title}"
    )
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(x_col.replace("_", " "), fontsize=11, labelpad=8)
    ax.set_ylabel(metric.replace("_", " ").title(), fontsize=11, labelpad=8)
    # Scenario names bisa panjang → rotasi lebih besar
    rotation = 40 if x_col == "Scenario" else 30
    ax.tick_params(axis="x", rotation=rotation)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Legend hanya ditampilkan jika ada hue (multi-skenario pada grafik perbandingan)
    legend = ax.get_legend()
    if legend is not None and hue_col is not None:
        ax.legend(
            title="Scenario",
            bbox_to_anchor=(1.01, 1),
            loc="upper left",
            borderaxespad=0,
            framealpha=0.9,
        )
    elif legend is not None:
        legend.remove()  # hapus legend kosong

    # ── 6. Simpan ─────────────────────────────────────────────────────────────
    plt.tight_layout()
    try:
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        rel_path = os.path.relpath(out_path, REPO_ROOT)
        print(f"\n  ✓ Grafik disimpan  →  {rel_path}")
        print(f"     Nama file   : {filename}")
        print(f"     Algoritma   : {algo_title}")
        print(f"     Skenario    : {scn_title}")
        print(f"     Metrik      : {metric}")
        print(f"     Grafik      : {chart_label}")
        print(
            f"     Data        : {len(plot_df)} baris  |  "
            f"{plot_df['Algorithm'].nunique()} algoritma  |  "
            f"{plot_df['Scenario'].nunique()} skenario"
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


def _prompt_list(
    heading: str,
    items: list[str],
    all_label: str | None = None,
) -> tuple[str | None, int]:
    """
    Tampilkan daftar items dan kembalikan (item_terpilih, index).

    all_label:
        Jika di-set, opsi 0 ditampilkan sebagai pilihan "semua".
        Jika None, user harus memilih salah satu item (tidak ada opsi "semua").

    Returns:
        (None, 0)    → user memilih opsi "semua" (hanya jika all_label di-set)
        (item, idx)  → user memilih item[idx-1]  (idx 1-based)
    """
    print(f"\n{heading}")
    print()
    if all_label is not None:
        print(f"    {'0':>2}. {all_label}")
    for i, item in enumerate(items, 1):
        print(f"    {i:>2}. {item}")
    print()
    print("     q. Keluar")

    lo = 0 if all_label is not None else 1
    hi = len(items)

    while True:
        raw = input("\n  Pilihan Anda: ").strip().lower()
        if raw == "q":
            print("\n  Keluar dari program.")
            sys.exit(0)
        try:
            idx = int(raw)
            if lo <= idx <= hi:
                if idx == 0:
                    return None, 0
                return items[idx - 1], idx
        except ValueError:
            pass
        print(f"  [!] Masukkan angka {lo}–{hi}.\n")


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

    # ── Loop Utama ─────────────────────────────────────────────────────────────
    while True:
        # ── [1/5] Pilih Topologi ──────────────────────────────────────────────
        _, topo_label, topo_key = _prompt_choice(
            "[1/5]  Pilih Topologi:", TOPOLOGY_OPTIONS
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

        all_algorithms = sorted(df["Algorithm"].unique().tolist())
        all_metrics = sorted(df["Metric"].unique().tolist())
        print(
            f"  ✓ Data dimuat: {len(df)} baris  |  "
            f"{len(all_metrics)} metrik  |  "
            f"{len(all_algorithms)} algoritma  |  "
            f"{df['Scenario'].nunique()} skenario"
        )

        # ── [2/5] Pilih Algoritma ───────────────────────────────────────────────
        print("\n[2/5]  Pilih Algoritma:")
        algo_filter, _ = _prompt_list(
            "  Algoritma yang tersedia:",
            all_algorithms,
            all_label="Semua Algoritma  (grafik perbandingan)",
        )
        algo_label = algo_filter or "Semua Algoritma"
        print(f"\n  ✓ Algoritma : {algo_label}")

        # Saring DataFrame untuk langkah berikutnya (metric & scenario discovery)
        view_df = df if algo_filter is None else df[df["Algorithm"] == algo_filter]

        # ── [3/5] Pilih Metrik ─────────────────────────────────────────────────
        metrics = sorted(view_df["Metric"].unique().tolist())
        print("\n[3/5]  Pilih Metrik  (dari kolom 'Metric'):")
        metric, _ = _prompt_list(
            "  Metrik yang tersedia:",
            metrics,
            all_label=None,  # harus pilih satu metrik
        )
        count = int((view_df["Metric"] == metric).sum())
        print(f"\n  ✓ Metrik    : '{metric}'  ({count} baris data)")

        # ── [4/5] Pilih Skenario ───────────────────────────────────────────────
        # Cari skenario yang relevan dengan metrik DAN algoritma yang sudah dipilih
        scenario_df = view_df[view_df["Metric"] == metric]
        scenarios = sorted(scenario_df["Scenario"].unique().tolist())
        print("\n[4/5]  Pilih Skenario:")
        scenario_filter, scenario_idx = _prompt_list(
            "  Skenario yang tersedia:",
            scenarios,
            all_label="Semua Skenario  (gabungan, idx = 0)",
        )
        scn_label = scenario_filter or "Semua Skenario"
        print(f"\n  ✓ Skenario  : {scn_label}  (idx = {scenario_idx})")

        # ── [5/5] Pilih Jenis Grafik ───────────────────────────────────────────
        _, chart_label, chart_type = _prompt_choice(
            "[5/5]  Pilih Jenis Grafik:", CHART_OPTIONS
        )
        print(f"\n  ✓ Grafik    : {chart_label}")

        # ── Preview nama file yang akan dibuat ────────────────────────────────
        algo_part = algo_filter or "all"
        preview_name = (
            f"{algo_part}_{metric}_{scenario_idx}_{_CHART_PREFIX[chart_type]}.png"
        )
        preview_path = os.path.join("visualize", topo_key, metric, preview_name)
        print(f"\n  ▸  Output   : {preview_path}")

        # ── Buat & Simpan Grafik ──────────────────────────────────────────────
        _sep()
        print(f"  Membuat {chart_label}...")

        make_plot(
            df=df,
            metric=metric,
            chart_type=chart_type,
            chart_label=chart_label,
            topo_label=topo_label,
            topo_key=topo_key,
            algo_filter=algo_filter,
            scenario_filter=scenario_filter,
            scenario_idx=scenario_idx,
        )

        # ── Lanjut? ─────────────────────────────────────────────────────────────
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
