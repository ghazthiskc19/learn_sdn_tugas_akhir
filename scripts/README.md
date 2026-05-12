# SDN Experiment Documentation

Dokumen ini adalah panduan tunggal untuk menjalankan, membandingkan, dan mengembangkan eksperimen di folder scripts.

## Struktur Folder

Folder scripts dibagi menjadi dua bagian utama:

- experiment_system/
	- Utility runner, orchestrator, pembanding topologi, dan post-processing.
- experiments/
	- Entry point eksperimen berbasis topologi (hierarchy dan mesh) plus file konfigurasi YAML.

## Quick Start

Jalankan launcher menu sederhana:

```bash
python3 scripts/experiment_system/run_experiment.py
```

Atau langsung jalankan semua eksperimen lintas topologi:

```bash
python3 scripts/experiment_system/run_all_experiments.py
```

## Cara Pakai Eksperimen Standalone

Kalau mau menjalankan eksperimen langsung tanpa launcher, jalankan dari root repo: `/workspaces/learn_sdn`.

Semua hasil CSV sekarang disimpan di struktur statis:

```
scripts/experiments/results/
├── hierarchy/
│   ├── convergence/           (CSV dari experiment_convergence_route.py)
│   ├── latency/               (CSV dari experiment_latency_e2e.py)
│   ├── throughput/            (CSV dari experiment_throughput.py)
│   └── hopcount/              (CSV dari experiment_hop_count.py)
└── mesh/
    ├── convergence/           (CSV dari experiment_convergence_route.py)
    ├── latency/               (CSV dari experiment_latency_e2e.py)
    ├── throughput/            (CSV dari experiment_throughput.py)
    └── hopcount/              (CSV dari experiment_hop_count.py)
```

Jalankan eksperimen tanpa argumen (gunakan default path):

```bash
python3 scripts/experiments/<topology>/experiment_<metric>.py \
  --controller-cmd "python3 SPF/dijkstra_osken_controller.py --verbose"
```

Atau kalau controller dijalankan manual di terminal lain:

```bash
python3 scripts/experiments/<topology>/experiment_<metric>.py --no-controller
```

### Hierarchy

```bash
# Convergence
python3 scripts/experiments/hierarchy/experiment_convergence_route.py \
  --controller-cmd "python3 SPF/dijkstra_osken_controller.py --verbose"
# CSV tersimpan di: scripts/experiments/results/hierarchy/convergence/

# Latency
python3 scripts/experiments/hierarchy/experiment_latency_e2e.py \
  --controller-cmd "python3 SPF/dijkstra_osken_controller.py --verbose"
# CSV tersimpan di: scripts/experiments/results/hierarchy/latency/

# Throughput
python3 scripts/experiments/hierarchy/experiment_throughput.py \
  --controller-cmd "python3 SPF/dijkstra_osken_controller.py --verbose"
# CSV tersimpan di: scripts/experiments/results/hierarchy/throughput/

# Hop count
python3 scripts/experiments/hierarchy/experiment_hop_count.py \
  --controller-cmd "python3 SPF/dijkstra_osken_controller.py --verbose"
# CSV tersimpan di: scripts/experiments/results/hierarchy/hopcount/
```

### Mesh

```bash
# Convergence
python3 scripts/experiments/mesh/experiment_convergence_route.py \
  --controller-cmd "python3 SPF/dijkstra_osken_controller.py --verbose"
# CSV tersimpan di: scripts/experiments/results/mesh/convergence/

# Latency
python3 scripts/experiments/mesh/experiment_latency_e2e.py \
  --controller-cmd "python3 SPF/dijkstra_osken_controller.py --verbose"
# CSV tersimpan di: scripts/experiments/results/mesh/latency/

# Throughput
python3 scripts/experiments/mesh/experiment_throughput.py \
  --controller-cmd "python3 SPF/dijkstra_osken_controller.py --verbose"
# CSV tersimpan di: scripts/experiments/results/mesh/throughput/

# Hop count
python3 scripts/experiments/mesh/experiment_hop_count.py \
  --controller-cmd "python3 SPF/dijkstra_osken_controller.py --verbose"
# CSV tersimpan di: scripts/experiments/results/mesh/hopcount/
```

Untuk meng-override output directory, pakai `--output-dir`:

```bash
python3 scripts/experiments/hierarchy/experiment_convergence_route.py \
  --no-controller --output-dir /tmp/custom-results
```

Opsi umum:

- `--verbose` untuk menampilkan log lebih detail.
- `--no-controller` kalau controller dijalankan terpisah.
- `--output-dir` untuk memindahkan hasil ke folder lain (override default).
- `--algo-name` untuk label algoritma di nama file CSV.

Output yang dibuat oleh skrip standalone:

- CSV agregat: `<algo>_<metric>_0.csv` (contoh: `dijkstra_convergence_0.csv`).
- CSV per skenario: `<algo>_<metric>_<scenario>.csv` (contoh: `dijkstra_convergence_1.csv`, `astar_latency_2.csv`).

```bash
# Hierarchy
python3 scripts/experiment_system/experiment_runner.py scripts/experiments/hierarchy.yaml

# Mesh
python3 scripts/experiment_system/experiment_runner.py scripts/experiments/mesh.yaml
```

Launcher mode langsung tanpa menu:

```bash
# Hierarchy
python3 scripts/experiment_system/run_experiment.py --topology hierarchy --metric convergence
python3 scripts/experiment_system/run_experiment.py --topology hierarchy --metric latency
python3 scripts/experiment_system/run_experiment.py --topology hierarchy --metric throughput
python3 scripts/experiment_system/run_experiment.py --topology hierarchy --metric hopcount

# Mesh
python3 scripts/experiment_system/run_experiment.py --topology mesh --metric convergence
python3 scripts/experiment_system/run_experiment.py --topology mesh --metric latency
python3 scripts/experiment_system/run_experiment.py --topology mesh --metric throughput
python3 scripts/experiment_system/run_experiment.py --topology mesh --metric hopcount
```

Contoh opsi tambahan:

```bash
python3 scripts/experiment_system/run_experiment.py --topology hierarchy --metric throughput --verbose
python3 scripts/experiment_system/run_experiment.py --topology hierarchy --metric convergence --no-controller
python3 scripts/experiment_system/run_experiment.py --topology hierarchy --metric latency --controller-cmd "python3 SPF/dijkstra_osken_controller.py --verbose"
```

## Ringkasan Komponen Utama

Di experiment_system/:

- experiment_runner.py
	- Engine utama untuk membangun topologi, menjalankan workload/event, dan mengumpulkan metrik.
- run_experiment.py
	- Launcher sederhana berbasis menu atau argumen.
- run_all_experiments.py
	- Orchestrator batch untuk banyak topologi sekaligus.
- compare_topologies.py
	- Pembanding hasil antar topologi.
- postprocess_results.py
	- Generator CSV, plot, dan summary statistik.
- metrics.py
	- Parser output ping/iperf/traceroute dan helper metrik.

Di experiments/:

- hierarchy/
	- Eksperimen khusus topologi hierarchy.
- mesh/
	- Eksperimen khusus topologi mesh.
- hierarchy.yaml, mesh.yaml, dan konfigurasi lain.

## Topology Comparison

Framework mendukung dua topologi utama:

| Topology | Switches | Hosts | Description |
|----------|----------|-------|-------------|
| hierarchy | 15 | 12 | 3-tier enterprise network (core/distribution/access) |
| mesh | 6 | 8 | Full-mesh topology untuk multipath/ECMP |

Jalankan perbandingan lintas topologi:

```bash
python3 scripts/experiment_system/run_all_experiments.py
```

Hasil default:

- results/hierarchy/
- results/mesh/
- comparison/

Jika hasil sudah ada, buat plot perbandingan saja:

```bash
python3 scripts/experiment_system/compare_topologies.py results/ --all
```

Opsi umum compare_topologies.py:

- --all
- --table
- --plots
- --output-dir

## Fitur dan Metrik

Jenis workload:

- throughput (TCP iperf)
- udp_burst (burst UDP)

Mode traffic:

- Single flow
- Concurrent flows
- Route convergence test (link down/up)

Metrik:

- Throughput (Mbps)
- Latency (ms)
- Packet loss (%)
- Hop count
- Route convergence time (detik)
- Event controller (PATH-COMPUTED dari log)

## Output yang Dihasilkan

Per run (sesuai folder output di config):

- results.json
- results.csv
- summary.txt
- controller.log
- file plot PNG (misalnya throughput_comparison.png, latency_distribution.png, convergence_times.png)

Contoh post-processing manual:

```bash
python3 scripts/experiment_system/postprocess_results.py results/hierarchy/results.json --all
python3 scripts/experiment_system/postprocess_results.py results/hierarchy/results.json --csv --plots --summary
python3 scripts/experiment_system/postprocess_results.py results/hierarchy/results.json --csv --summary
```

## Contoh Konfigurasi YAML

```yaml
topology: hierarchy
controller:
	cmd: python3 SPF/dijkstra_osken_controller.py --verbose

workloads:
	- name: "bulk-tcp"
		src: "Host1"
		dst: "Host12"
		type: "throughput"
		proto: tcp
		duration: 10
		start_delay: 2

	- name: "video-stream"
		src: "Host2"
		dst: "Host11"
		type: "udp_burst"
		bitrate: "5M"
		burst_duration: 2
		burst_count: 5
		interval_between: 1

concurrent_flows:
	- ["Host1", "Host12", "tcp"]
	- ["Host3", "Host11", "udp"]
	- ["Host4", "Host10", "tcp"]

concurrent_duration: 5

events:
	- name: "test-convergence"
		action: link-down
		src_switch: "s4"
		dst_switch: "s5"
		at: 5
		duration: 2

trials: 2
output: results/hierarchy
```

## Integrasi Eksperimen (Status)

Saat ini pendekatan yang dipakai adalah standalone scripts per eksperimen di bawah experiments/hierarchy/ dan experiments/mesh/, sedangkan experiment_system/ berfungsi sebagai framework runner + analisis.

Rekomendasi sekarang:

1. Jalankan dan validasi tiap eksperimen secara independen.
2. Gunakan postprocess_results.py untuk visualisasi/rekap.
3. Gunakan run_all_experiments.py dan compare_topologies.py untuk perbandingan lintas topologi.

## Detail Eksperimen 1: Route Convergence

Script:

- scripts/experiments/hierarchy/experiment_convergence_route.py

Tujuan:

- Mengukur route convergence time Host1 ke Host9 pada topologi hierarchy.

Empat skenario:

1. Cold-Start Convergence
2. Core Failure Convergence
3. Edge Failure Convergence
4. Node Failure Convergence

Contoh jalankan:

```bash
python3 scripts/experiments/hierarchy/experiment_convergence_route.py
python3 scripts/experiments/hierarchy/experiment_convergence_route.py --output-dir results/convergence_test
python3 scripts/experiments/hierarchy/experiment_convergence_route.py --controller-cmd "python3 SPF/astar_osken_controller.py --verbose"
python3 scripts/experiments/hierarchy/experiment_convergence_route.py --no-controller
```

Format CSV hasil convergence:

```csv
Scenario,Convergence_Time_Seconds,Status
Cold-Start,2.345,SUCCESS
Core Failure,1.234,SUCCESS
Edge Failure,0.876,SUCCESS
Node Failure,3.456,SUCCESS
```

Interpretasi cepat:

- < 1s: sangat cepat
- 1-2s: baik
- 2-5s: masih dapat diterima
- > 5s: perlu optimasi
- timeout/None: indikasi isu controller/topologi

## Standar Format CSV per Eksperimen

Eksperimen 1 (convergence):

```csv
Scenario,Convergence_Time_Seconds,Status
```

Eksperimen 2 (latency) target:

```csv
Source,Destination,Latency_Ms,Status
```

Eksperimen 3 (throughput) target:

```csv
Source,Destination,Throughput_Mbps,Workload,Status
```

Eksperimen 4 (hop count) target:

```csv
Source,Destination,Hop_Count,Path,Status
```

## Troubleshooting

Controller gagal connect:

- Pastikan RemoteController aktif di localhost:6633.
- Cek command controller di YAML.
- Cek controller.log.

Host tidak ditemukan:

- Cek nama host di YAML sesuai topologi (hierarchy: Host1-Host12, mesh: Host1-Host8).

Plot comparison kosong:

- Pastikan results.json ada di subfolder topologi.
- Pastikan eksperimen selesai penuh.

Matplotlib tidak tersedia:

- Plot dilewati otomatis, CSV dan summary tetap dibuat.
- Install: pip install matplotlib

## Pengembangan Lanjutan

Tambah topologi baru:

1. Tambah builder baru di experiment_runner.py (misalnya build_mytopo).
2. Register handler topology baru di main().
3. Buat YAML baru di scripts/experiments/.
4. Jalankan via experiment_runner.py.

Tambah workload/plot baru:

1. Update parser/logic di metrics.py atau experiment_runner.py.
2. Tambah fungsi plot di postprocess_results.py.
3. Validasi output JSON/CSV/summary tetap konsisten.
