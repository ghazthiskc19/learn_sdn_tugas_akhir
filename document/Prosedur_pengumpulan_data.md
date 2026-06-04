# Prosedur Pengumpulan Data

Proses pengumpulan data dilaksanakan secara sistematis dan terotomatisasi untuk menjaga konsistensi, reprodusibilitas, serta validitas hasil eksperimen. Seluruh pengujian berjalan pada lingkungan virtual berbasis Mininet dengan controller SDN OSKen (Ryu compatible) yang mengeksekusi algoritme routing secara terpisah pada setiap skenario. Algoritme yang dibandingkan meliputi BFS, Dijkstra, A*, dan Bellman-Ford.

Secara umum alur pengujian adalah: menyiapkan topologi, menjalankan controller, melakukan traffic uji, mengekstrak metrik dari data plane dan log controller, kemudian menyimpan hasil ke CSV. Struktur ini diterapkan secara konsisten pada seluruh skenario agar perbandingan lintas algoritme dan topologi bersifat adil. Perbedaan antar skenario hanya terletak pada jenis traffic dan metrik utama yang diukur.

Dalam laporan ini, penamaan host mengikuti konvensi Host A1 sebagai sumber dan Host B2 sebagai tujuan. Pada implementasi, pasangan tersebut ekuivalen dengan Host1-Host4 (topologi Hierarchy) dan HostA-HostD (topologi Mesh).

## A. Konfigurasi weight

Eksperimen menggunakan weight dalam dua bentuk: delay_ms untuk pengukuran latency dan convergence, serta bandwidth_mbps untuk pengukuran throughput. Tujuan penerapan weight adalah memverifikasi apakah algoritme benar-benar melakukan kalkulasi cost berbobot atau sekadar memilih jalur dengan hop minimum. BFS dijalankan tanpa weight, sedangkan Dijkstra, A*, dan Bellman-Ford menggunakan weight dari file konfigurasi.

Bobot disediakan pada masing-masing file eksperimen sesuai kebutuhan skenario, lalu diinjeksi ke controller sebelum proses berjalan. Injeksi dilakukan melalui environment variable SPF_WEIGHTS_FILE dan SPF_WEIGHT_FIELD sehingga setiap eksperimen memakai bobot yang konsisten dan dapat direproduksi.

## B. Load topology dan controller

Sebelum pengambilan data, controller dijalankan lebih dahulu dan sistem menunggu hingga koneksi TCP OpenFlow siap. Setelah itu topologi Mininet dibuat dengan auto MAC dan auto ARP agar pembelajaran host berjalan stabil. Pada beberapa skenario, IPv6 dinonaktifkan untuk mengurangi noise trafik non-ICMP. Selanjutnya dilakukan warm-up berupa ping singkat untuk memicu Packet-In dan Flow-Mod, sehingga jalur forwarding telah terpasang sebelum data utama diambil.

## C. Skenario eksperimen

### a. Pengujian skenario 1 (Latency)

Skenario pertama dijalankan pada topologi Hierarchy dan Mesh tanpa interupsi jaringan. Pengambilan data dilakukan dengan mengirimkan 50 paket ICMP dari host sumber ke host tujuan. Lima paket pertama ditetapkan sebagai warm-up dan dikeluarkan dari analisis, sehingga sampel yang dianalisis berjumlah 45 RTT. Pemotongan ini bertujuan mengeliminasi delay inisialisasi yang berasal dari control plane.

Nilai RTT digunakan langsung sebagai metrik round-trip latency. Selain itu, hop count dihitung dengan melacak jalur forwarding pada log controller untuk membandingkan efisiensi jalur antar algoritme.

### b. Pengujian skenario 2 (Throughput)

Skenario kedua mengevaluasi kemampuan algoritme dalam menghindari jalur dengan bandwidth rendah. Link pada topologi dimodifikasi agar memiliki variasi kapasitas. Pengambilan data dilakukan menggunakan iperf3 dengan protokol TCP selama 20 detik, dengan interval pelaporan 1 detik. Sebelum iperf3 dijalankan, dilakukan ping sebanyak 10 kali untuk memastikan flow telah terpasang pada data plane.

Pada skenario ini, algoritme berbobot menghitung cost berdasarkan bandwidth dengan referensi 1000 Mbps sebagai kapasitas maksimum topologi. Throughput end-to-end yang dihasilkan digunakan untuk menilai efektivitas pemilihan jalur berbobot dibanding jalur dengan hop minimum.

### c. Pengujian skenario 3 (Convergence)

Skenario convergence terdiri dari dua sub-skenario. Sub-skenario A melakukan flap pada salah satu link di topologi Hierarchy untuk memicu event Port_Status. Metrik utama adalah convergence_ms yang diambil dari log controller sebagai waktu konvergensi rute setelah perubahan link.

Sub-skenario B menjalankan phantom graph in-memory berukuran 500 node dan 2000 edge untuk mengukur computation_time_us secara murni tanpa pengaruh data plane. Selain waktu komputasi, dicatat metrik pencarian seperti nodes_visited (jumlah node yang dieksplorasi), queue_pops atau heap_pops (jumlah operasi pada struktur antrian/prioritas), dan relaxations (jumlah pembaruan cost). Metrik ini penting untuk menggambarkan beban algoritme dan kompleksitas pencarian selain angka waktu konvergensi.

## D. Hasil pengumpulan data

Seluruh hasil disimpan dalam bentuk CSV per topologi dan skenario. Setiap baris data memuat algoritme, metrik utama (rtt_ms, bits_per_second, atau convergence_ms), serta atribut pendukung seperti hop_count dan path. Untuk throughput, data disimpan per detik; untuk latency, data disimpan per paket; untuk convergence, data disimpan per kejadian konvergensi dan perhitungan phantom graph. Penyimpanan dilakukan otomatis oleh script setelah eksperimen selesai.

## E. Visualisasi data

Tahap visualisasi dimulai dengan membaca file CSV hasil eksperimen. Untuk skenario latency, data warm-up (5 paket pertama) difilter agar tidak ikut dianalisis. Selanjutnya dilakukan agregasi rata-rata dan analisis distribusi. Visualisasi yang digunakan meliputi boxplot atau histogram untuk sebaran RTT, line chart untuk throughput per detik, serta bar chart atau boxplot untuk membandingkan convergence time antar algoritme.

Preprocessing dilakukan secara minimal dan terkontrol, mencakup konversi tipe data numerik, penghapusan entri kosong, serta pengelompokan berdasarkan algoritme. Dengan alur ini, hasil visualisasi tetap konsisten dan layak digunakan pada laporan akhir.
