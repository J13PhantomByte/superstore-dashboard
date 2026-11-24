# Superstore Sales Dashboard

Dashboard analisis penjualan interaktif berbasis **Python, Streamlit, Pandas, dan Plotly**.
Seluruh angka dihitung langsung dari file `clear train.csv` (mata uang USD).

## Struktur Project

```text
superstore-dashboard/
├── app.py
├── clear train.csv
├── requirements.txt
└── README.md
```

## Instalasi dan Menjalankan (Terminal VS Code)

1. Buka folder `superstore-dashboard` di VS Code, lalu buka terminal (`Ctrl + ` `).
2. (Disarankan) buat virtual environment:

   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS / Linux
   source venv/bin/activate
   ```

3. Pasang library dan jalankan:

   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

4. Browser akan terbuka otomatis di `http://localhost:8501`.

## Fitur

- **Filter:** rentang tanggal pesanan, Region, Kategori, Segmen, dan tombol Reset Filter.
- **KPI:** Produk Terlaris (berdasarkan SUM Sales), Total Sales, Total Orders (`nunique` Order ID).
- **Analisis 1:** Top 10 produk (horizontal bar chart) + insight otomatis.
- **Analisis 2:** Kontribusi kategori (donut chart) + insight otomatis.
- **Analisis 3:** Tren penjualan bulanan (line chart) + insight otomatis.
- **Ringkasan Analisis Penjualan** yang dibuat dinamis mengikuti filter aktif.

## Penjelasan Kode (`app.py`)

| Bagian | Fungsi |
|---|---|
| Format & utilitas | `usd`, `angka`, `persen`, `nama_bulan`, `tanggal_id` agar format angka konsisten |
| Pemuatan data | `load_data` (di-cache): validasi kolom, konversi `Order Date` dan `Sales`, hapus duplikat yang identik di semua kolom |
| Filter | `apply_filters` menerapkan semua filter sekaligus |
| Agregasi | `product_sales`, `category_sales`, `monthly_sales` |
| Insight | `insight_produk`, `insight_kategori`, `insight_tren`, `ringkasan` menghasilkan teks dari hasil perhitungan |
| Grafik | `chart_top_produk`, `chart_kategori`, `chart_tren` (Plotly) |
| Tampilan | `CSS`, `kpi_card`, `section`, `insight_box` |
| Sidebar | `init_filter_state`, `render_sidebar`, `reset_filters` (memakai `st.session_state`) |
| `main` | Merangkai seluruh halaman dan menangani error / filter kosong |

## Keterbatasan Data

- Dataset tidak memiliki kolom `Quantity` dan `Profit`, sehingga tidak ada analisis jumlah unit atau keuntungan.
- Produk terlaris diukur dari total nilai penjualan, bukan jumlah unit.
- Kolom `Postal Code` memiliki beberapa nilai kosong; kolom ini tidak dipakai dalam analisis.
- Insight tren hanya menggambarkan arah umum data, bukan penyebab perubahan atau pola musiman.
