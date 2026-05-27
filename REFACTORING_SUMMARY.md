# Refactoring Summary: Time-Series Visualization & Data Extraction

## 📋 Status Update (13 Mei 2026)

Semua komponen refaktor sudah **SELESAI** dan **TERUJI** sesuai requirement:

### ✅ Phase 1: Data Extraction (Already Completed)

**Struktur CSV baru untuk semua eksperimen:**
```
Topology, Algorithm, Metric, Scenario, Time_Seq, Value
```

**Status per topologi:**

#### Hierarchy Topology ✅
- ✅ `experiment_convergence_route.py` - Parse ping per-sequence, RTO=-1
- ✅ `experiment_throughput.py` - Parse iperf3 per-detik, 2 metrik (Throughput + Retransmits)
- ✅ `experiment_hop_count.py` - Menggunakan ts_utils.make_row()
- ✅ `experiment_latency_e2e.py` - Parse ping per-sequence

#### Mesh Topology ✅
- ✅ `experiment_convergence_route.py` - Parse ping per-sequence, RTO=-1
- ✅ `experiment_throughput.py` - Parse iperf3 per-detik
- ✅ `experiment_hop_count.py` - Menggunakan ts_utils.make_row()
- ✅ `experiment_latency_e2e.py` - Parse ping per-sequence

**Utility Module:**
- ✅ `ts_utils.py` - Central parsing & CSV writing:
  - `parse_ping_timeseries()` - Handle timeout (-1.0)
  - `parse_iperf3_timeseries()` - Per-second extraction
  - `rows_from_ping()`, `rows_from_iperf3()` - Row builders
  - `save_timeseries()` - CSV writer

---

### ✅ Phase 2: Interactive Visualization (Just Completed)

**Script baru: `visualize_timeseries.py`** ✨

#### Fitur:
1. **CLI Interaktif** untuk memilih:
   - Topologi (mesh / hierarchy)
   - Metrik (latency_ms, Throughput_Mbps, Retransmits, hop_count)
   - Skenario (Cold-Start, Core Failure, dll.)
   - Jenis plot (Time-Series / Density / Boxplot)

2. **3 Jenis Plot untuk Analisis Algoritma:**

   **A. Time-Series Line Plot**
   - X = Time_Seq (packet ke- atau detik ke-)
   - Y = Value (latency, throughput, dll.)
   - Hue = Algorithm (garis warna per algoritma)
   - ✨ Marker pada setiap point
   - ✨ Timeout marker (x) untuk ping RTO
   - ✨ **Jelas menunjukkan spike/penurunan saat failure**

   **B. Density Plot (KDE)**
   - X = Value
   - Y = Density (probability density function)
   - Hue = Algorithm (area fill)
   - ✨ `fill=True` untuk area under curve
   - ✨ Timeout (-1.0) di-filter
   - ✨ **Bandingkan consistency/spread antar algoritma**

   **C. Boxplot**
   - X = Algorithm
   - Y = Value
   - ✨ Kotak Q1-Q3, garis median, whisker 1.5×IQR
   - ✨ Outlier ditampilkan sebagai titik
   - ✨ **Ringkasan statistik per algoritma**

3. **Penanganan Data Khusus:**
   - ✅ Latency timeout (Value = -1.0):
     - Time-Series: tampilkan garis putus + marker
     - Density/Boxplot: filter otomatis
   - ✅ Filter receiver/summary lines iperf3
   - ✅ Normalisasi unit (Kbps → Mbps)

4. **Output Professional:**
   - ✅ DPI=300 (print-ready untuk laporan)
   - ✅ Direktori rapi: `visualize/{topology}/{metric}/{scenario}_{plot_type}.png`
   - ✅ Large figsize (14×6 untuk clarity)

#### Mode Operasi:
- **Interactive Mode (default):** Guided menu
- **Batch Mode:** Non-interactive untuk scripting
  ```bash
  python3 scripts/visualize/visualize_timeseries.py --batch \
    --topology hierarchy --metric latency_ms --plot-type timeseries
  ```

---

## 📁 Struktur File yang Dihasilkan

```
scripts/
├── experiments/
│   ├── results/
│   │   ├── hierarchy/
│   │   │   ├── convergence/*.csv (latency_ms per packet)
│   │   │   ├── throughput/*.csv (Throughput_Mbps, Retransmits per detik)
│   │   │   ├── hopcount/*.csv (hop_count per test)
│   │   │   └── latency/*.csv (latency_ms per packet)
│   │   └── mesh/
│   │       ├── convergence/*.csv
│   │       ├── throughput/*.csv
│   │       ├── hopcount/*.csv
│   │       └── latency/*.csv
│   ├── ts_utils.py ⭐ (Central parsing utility)
│   └── hierarchy/, mesh/
│       ├── experiment_convergence_route.py ✅
│       ├── experiment_throughput.py ✅
│       ├── experiment_hop_count.py ✅
│       └── experiment_latency_e2e.py ✅
│
└── visualize/
    ├── visualize_timeseries.py ⭐ (New interactive script)
    ├── QUICKSTART.md ⭐ (Quick start guide)
    ├── README-TIMESERIES.md ⭐ (Full documentation)
    ├── hierarchy/
    │   ├── latency_ms/*.png
    │   ├── Throughput_Mbps/*.png
    │   └── hop_count/*.png
    └── mesh/
        ├── latency_ms/*.png
        ├── Throughput_Mbps/*.png
        └── hop_count/*.png
```

---

## 🚀 Cara Menggunakan

### Setup (1x saja)
```bash
pip install pandas matplotlib seaborn numpy
```

### Mode Interaktif (Rekomendasi)
```bash
cd /workspaces/learn_sdn
python3 scripts/visualize/visualize_timeseries.py

# Menu:
# 1. Pilih topology
# 2. Pilih metric
# 3. Pilih scenario
# 4. Pilih plot type
```

### Mode Batch (untuk Reporting)
```bash
# Generate semua timeseries plot hierarchy latency
python3 scripts/visualize/visualize_timeseries.py --batch \
  --topology hierarchy --metric latency_ms --plot-type timeseries

# Generate density plot mesh throughput, skenario tertentu
python3 scripts/visualize/visualize_timeseries.py --batch \
  --topology mesh --metric Throughput_Mbps \
  --scenario "Baseline,Multi-Flow" --plot-type density

# Generate boxplot hierarchy hop_count
python3 scripts/visualize/visualize_timeseries.py --batch \
  --topology hierarchy --metric hop_count --plot-type boxplot
```

---

## 📊 Contoh Use Case untuk Laporan

### Figure 1: Route Convergence (Hierarchy)
```bash
# Time-Series: lihat spike/recovery speed saat Core Failure
python3 scripts/visualize/visualize_timeseries.py --batch \
  --topology hierarchy --metric latency_ms \
  --scenario "Core Failure" --plot-type timeseries
```
**Output:** `visualize/hierarchy/latency_ms/core_failure_timeseries.png`

**Interpretasi:** Garis mana yg paling cepat kembali ke baseline? → Algoritma itu paling responsif.

---

### Figure 2: Throughput Distribution (Mesh)
```bash
# Density: lihat consistency/fairness throughput
python3 scripts/visualize/visualize_timeseries.py --batch \
  --topology mesh --metric Throughput_Mbps \
  --scenario "Multi-Flow" --plot-type density
```
**Output:** `visualize/mesh/Throughput_Mbps/multi-flow_density.png`

**Interpretasi:** Kurva paling sempit = paling konsisten. Kurva lebar = fluktuatif.

---

### Figure 3: Hop Count Summary (Hierarchy)
```bash
# Boxplot: statistik ringkas hop count
python3 scripts/visualize/visualize_timeseries.py --batch \
  --topology hierarchy --metric hop_count --plot-type boxplot
```
**Output:** `visualize/hierarchy/hop_count/*_boxplot.png`

**Interpretasi:** Boxplot terendah = algoritma paling optimal pilih jalur pendek.

---

## ✨ Highlight Fitur

### Time-Series Plot
- ✅ Marker pada setiap data point (jelas)
- ✅ Garis putus untuk timeout (terlihat jelas)
- ✅ Timeout marker 'x' merah di top
- ✅ **Sangat cocok menunjukkan momen failure & recovery**

### Density Plot
- ✅ Area fill `fill=True` untuk visual jelas
- ✅ Timeout otomatis di-filter
- ✅ **Bandingkan consistency antar algoritma**

### Boxplot
- ✅ Q1-Q3 kotak, median garis, whisker, outlier
- ✅ **Ringkasan statistik professional**

---

## 🧪 Testing

Semua sudah di-test dan berfungsi:

```bash
# Test 1: Interactive mode (manual menu)
✓ Tested

# Test 2: Batch mode - timeseries
✓ Generated: hierarchy/latency_ms/*.png

# Test 3: Batch mode - density
✓ Generated: mesh/Throughput_Mbps/*.png

# Test 4: Batch mode - boxplot
✓ Generated: hierarchy/hop_count/*.png

# All PNG: DPI=300 ✓
# All sizes: ~300KB-1MB ✓
```

---

## 📝 Dokumentasi

### Untuk User
- 📄 `QUICKSTART.md` - Quick reference, contoh command
- 📄 `README-TIMESERIES.md` - Full documentation, penjelasan detail

### Di Script
- ✅ Docstring lengkap setiap fungsi
- ✅ Comments inline untuk logic kompleks
- ✅ Error handling yang informative

---

## 🎯 Next Steps (Optional)

Jika ingin extend di masa depan:

1. **Live Dashboard** - Real-time plot update
2. **Statistical Testing** - ANOVA, t-test antar algoritma
3. **Animation** - Animated time-series menunjukkan event
4. **Export to Latex** - Auto-generate laporan PDF

---

## Summary

| Aspek | Status | Catatan |
|---|---|---|
| Data Extraction | ✅ Done | 4 eksperimen × 2 topologi, all time-series |
| CSV Format | ✅ Done | [Topology, Algorithm, Metric, Scenario, Time_Seq, Value] |
| Visualization Script | ✅ Done | 3 jenis plot, CLI interactive + batch mode |
| Timeout Handling | ✅ Done | Filter dense plot, biarkan time-series |
| Documentation | ✅ Done | QUICKSTART + README + docstring |
| Testing | ✅ Done | All plot types tested, DPI=300 verified |

**Status Keseluruhan: ✅ COMPLETE & READY FOR REPORTING**

---

**Tanggal:** 13 Mei 2026
**Version:** 1.0 Final
