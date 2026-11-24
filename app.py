"""Superstore Sales Dashboard.

Dashboard interaktif berbasis Streamlit untuk menganalisis penjualan dari
file CSV 'clear train.csv'. Semua angka dihitung langsung dari dataset.
"""

from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
CSV_PATH = Path(__file__).parent / "clear train.csv"
REQUIRED_COLUMNS = [
    "Order ID", "Order Date", "Segment", "Region",
    "Category", "Product Name", "Sales",
]

NAVY = "#0B1F4B"
ROYAL = "#2563EB"
GRID = "#E2E8F0"
TEXT_MUTED = "#64748B"
CATEGORY_COLORS = {
    "Furniture": "#2563EB",       # royal blue
    "Office Supplies": "#0F766E", # teal
    "Technology": "#D97706",      # amber
}

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]

st.set_page_config(
    page_title="Superstore Sales Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Format & utilitas
# ---------------------------------------------------------------------------
def usd(value: float) -> str:
    """Format angka sebagai mata uang USD, mis. $1,234.56."""
    return f"${value:,.2f}"


def angka(value: float) -> str:
    """Format bilangan bulat dengan pemisah ribuan."""
    return f"{int(value):,}"


def persen(value: float) -> str:
    return f"{value:.1f}%"


def nama_bulan(periode: pd.Period) -> str:
    """Contoh: Period('2018-03') -> 'Maret 2018'."""
    return f"{BULAN[periode.month - 1]} {periode.year}"


def tanggal_id(d: date | pd.Timestamp) -> str:
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


# ---------------------------------------------------------------------------
# Pemuatan & pembersihan data
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Memuat data...")
def load_data(path: str) -> tuple[pd.DataFrame, int]:
    """Baca CSV, validasi kolom, ubah tipe data, dan hapus duplikat persis.

    Mengembalikan (DataFrame bersih, jumlah baris duplikat yang dihapus).
    Hanya baris yang identik di SEMUA kolom yang dianggap duplikat.
    """
    df = pd.read_csv(path)

    kolom_hilang = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if kolom_hilang:
        raise ValueError(f"Kolom wajib tidak ditemukan: {', '.join(kolom_hilang)}")

    df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")
    df["Sales"] = pd.to_numeric(df["Sales"], errors="coerce")

    # Baris tanpa tanggal/Sales valid tidak bisa dianalisis.
    df = df.dropna(subset=["Order Date", "Sales", "Order ID", "Product Name"])

    sebelum = len(df)
    df = df.drop_duplicates()
    duplikat = sebelum - len(df)

    return df.reset_index(drop=True), duplikat


def apply_filters(df: pd.DataFrame, start: date, end: date, regions: list,
                  categories: list, segments: list) -> pd.DataFrame:
    mask = (
        (df["Order Date"] >= pd.Timestamp(start))
        & (df["Order Date"] <= pd.Timestamp(end))
        & df["Region"].isin(regions)
        & df["Category"].isin(categories)
        & df["Segment"].isin(segments)
    )
    return df.loc[mask]


# ---------------------------------------------------------------------------
# Perhitungan KPI & agregasi
# ---------------------------------------------------------------------------
def product_sales(df: pd.DataFrame) -> pd.DataFrame:
    """Total Sales per Product Name, urut dari terbesar."""
    return (df.groupby("Product Name", as_index=False)["Sales"].sum()
              .sort_values("Sales", ascending=False)
              .reset_index(drop=True))


def category_sales(df: pd.DataFrame) -> pd.DataFrame:
    out = (df.groupby("Category", as_index=False)["Sales"].sum()
             .sort_values("Sales", ascending=False)
             .reset_index(drop=True))
    out["Persen"] = out["Sales"] / out["Sales"].sum() * 100
    return out


def monthly_sales(df: pd.DataFrame) -> pd.DataFrame:
    """Total Sales per bulan (tahun-bulan), kronologis.

    Bulan tanpa transaksi di antara bulan pertama dan terakhir diisi 0
    agar perbandingan 'bulan sebelumnya' selalu antar bulan yang berurutan.
    """
    per = df["Order Date"].dt.to_period("M")
    s = df.groupby(per)["Sales"].sum().sort_index()
    penuh = pd.period_range(s.index.min(), s.index.max(), freq="M")
    s = s.reindex(penuh, fill_value=0.0)
    out = s.rename_axis("Periode").reset_index()
    out["Label"] = out["Periode"].apply(nama_bulan)
    out["Tanggal"] = out["Periode"].dt.to_timestamp()
    return out


# ---------------------------------------------------------------------------
# Insight otomatis (teks dinamis)
# ---------------------------------------------------------------------------
def insight_produk(prod: pd.DataFrame, total_sales: float) -> list[str]:
    top = prod.iloc[0]
    teks = [
        f"**{top['Product Name']}** adalah produk dengan nilai penjualan "
        f"tertinggi, yaitu **{usd(top['Sales'])}** "
        f"({persen(top['Sales'] / total_sales * 100)} dari total penjualan)."
    ]
    if len(prod) > 1:
        kedua = prod.iloc[1]
        selisih = top["Sales"] - kedua["Sales"]
        rasio = top["Sales"] / kedua["Sales"] if kedua["Sales"] else np.nan
        teks.append(
            f"Dibandingkan peringkat kedua (**{kedua['Product Name']}**, "
            f"{usd(kedua['Sales'])}), produk peringkat pertama lebih tinggi "
            f"{usd(selisih)} atau sekitar {rasio:.2f} kali lipat."
        )
    top10 = prod.head(10)["Sales"].sum()
    teks.append(
        f"Sepuluh produk teratas bersama-sama menyumbang {usd(top10)} "
        f"({persen(top10 / total_sales * 100)} dari total penjualan)."
    )
    return teks


def insight_kategori(cat: pd.DataFrame) -> list[str]:
    tertinggi, terendah = cat.iloc[0], cat.iloc[-1]
    rincian = ", ".join(
        f"{r.Category} {usd(r.Sales)} ({persen(r.Persen)})"
        for r in cat.itertuples()
    )
    teks = [f"Kontribusi setiap kategori: {rincian}."]
    if len(cat) > 1:
        selisih_pp = tertinggi["Persen"] - terendah["Persen"]
        teks.append(
            f"Kategori tertinggi adalah **{tertinggi['Category']}** dan "
            f"terendah adalah **{terendah['Category']}**. Selisih penjualannya "
            f"{usd(tertinggi['Sales'] - terendah['Sales'])} "
            f"({selisih_pp:.1f} poin persentase)."
        )
        if tertinggi["Persen"] > 50:
            teks.append(
                f"{tertinggi['Category']} menyumbang lebih dari separuh "
                f"penjualan, sehingga paling dominan."
            )
        else:
            teks.append(
                f"{tertinggi['Category']} paling dominan, namun belum "
                f"mencapai separuh dari total penjualan."
            )
    else:
        teks.append(f"Hanya terdapat satu kategori: **{tertinggi['Category']}**.")
    return teks


def tren_label(m: pd.DataFrame) -> tuple[str, float]:
    """Arah tren berdasarkan kemiringan garis regresi linear.

    Mengembalikan (label, kemiringan relatif per bulan terhadap rata-rata).
    """
    if len(m) < 3:
        return "belum cukup data untuk menilai tren", 0.0
    x = np.arange(len(m))
    slope = np.polyfit(x, m["Sales"].to_numpy(), 1)[0]
    rata = m["Sales"].mean()
    rel = slope / rata * 100 if rata else 0.0
    if abs(rel) < 0.5:
        return "relatif datar", rel
    return ("cenderung meningkat" if slope > 0 else "cenderung menurun"), rel


def insight_tren(m: pd.DataFrame) -> list[str]:
    maks = m.loc[m["Sales"].idxmax()]
    mins = m.loc[m["Sales"].idxmin()]
    if len(m) == 1:
        teks = [f"Data yang dipilih hanya mencakup satu bulan: **{maks['Label']}** "
                f"dengan total penjualan **{usd(maks['Sales'])}**."]
    else:
        teks = [
            f"Penjualan bulanan tertinggi terjadi pada **{maks['Label']}** "
            f"sebesar **{usd(maks['Sales'])}**, sedangkan terendah pada "
            f"**{mins['Label']}** sebesar **{usd(mins['Sales'])}**."
        ]
    if len(m) >= 2:
        akhir, sebelumnya = m.iloc[-1], m.iloc[-2]
        delta = akhir["Sales"] - sebelumnya["Sales"]
        arah = "naik" if delta > 0 else "turun" if delta < 0 else "tidak berubah"
        kalimat = (
            f"Pada bulan terakhir ({akhir['Label']}), penjualan {arah} "
            f"dibandingkan {sebelumnya['Label']}"
        )
        if delta != 0:
            kalimat += f" sebesar {usd(abs(delta))}"
            if sebelumnya["Sales"] > 0:
                kalimat += f" ({abs(delta) / sebelumnya['Sales'] * 100:.1f}%)"
        teks.append(kalimat + ".")
        naik = int((m["Sales"].diff().dropna() > 0).sum())
        turun = int((m["Sales"].diff().dropna() < 0).sum())
        teks.append(
            f"Dari {len(m) - 1} perubahan bulan ke bulan, {naik} bulan naik "
            f"dan {turun} bulan turun, sehingga penjualan bersifat fluktuatif."
            if naik and turun else
            f"Dari {len(m) - 1} perubahan bulan ke bulan, {naik} bulan naik "
            f"dan {turun} bulan turun."
        )
    label, rel = tren_label(m)
    if len(m) >= 3:
        teks.append(
            f"Berdasarkan garis tren linear, penjualan bulanan **{label}** "
            f"(sekitar {rel:+.1f}% dari rata-rata bulanan per bulan). "
            f"Ini hanya menggambarkan arah umum, bukan penyebab perubahan."
        )
    else:
        teks.append("Data kurang dari 3 bulan, sehingga tren belum dapat dinilai.")
    return teks


def ringkasan(prod: pd.DataFrame, cat: pd.DataFrame, m: pd.DataFrame,
              total_sales: float, total_orders: int, n_produk: int) -> list[str]:
    top = prod.iloc[0]
    kat = cat.iloc[0]
    label, _ = tren_label(m)
    maks = m.loc[m["Sales"].idxmax()]
    rata_order = total_sales / total_orders if total_orders else 0
    return [
        f"**1. Produk dengan penjualan tertinggi:** {top['Product Name']} "
        f"dengan total {usd(top['Sales'])}.",
        f"**2. Kategori paling berkontribusi:** {kat['Category']} sebesar "
        f"{usd(kat['Sales'])} ({persen(kat['Persen'])} dari total penjualan).",
        f"**3. Perkembangan penjualan:** tren bulanan {label}; puncak penjualan "
        f"pada {maks['Label']} ({usd(maks['Sales'])}).",
        f"**4. Temuan utama:** pada data yang dipilih terdapat "
        f"{angka(total_orders)} pesanan unik dengan total penjualan "
        f"{usd(total_sales)} dari {angka(n_produk)} produk berbeda. "
        f"Rata-rata nilai penjualan per pesanan adalah {usd(rata_order)}.",
    ]


# ---------------------------------------------------------------------------
# Grafik
# ---------------------------------------------------------------------------
def _layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, Arial, sans-serif", color=NAVY, size=13),
        hoverlabel=dict(bgcolor="white", font_size=13, bordercolor=GRID),
    )
    return fig


def chart_top_produk(prod: pd.DataFrame) -> go.Figure:
    top = prod.head(10).copy()
    top["Label"] = top["Product Name"].apply(
        lambda s: s if len(s) <= 42 else s[:41].rstrip() + "…")
    fig = go.Figure(go.Bar(
        x=top["Sales"], y=top["Label"], orientation="h",
        marker=dict(color=ROYAL),
        customdata=top["Product Name"],
        text=top["Sales"].apply(usd), textposition="outside", cliponaxis=False,
        hovertemplate="<b>%{customdata}</b><br>Total Sales: $%{x:,.2f}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", title=None, automargin=True)
    fig.update_xaxes(title="Total Sales (USD)", tickprefix="$", tickformat=",",
                     gridcolor=GRID, zeroline=False)
    fig.update_layout(bargap=0.3)
    return _layout(fig, 460)


def chart_kategori(cat: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=cat["Category"], values=cat["Sales"], hole=0.58, sort=False,
        marker=dict(colors=[CATEGORY_COLORS.get(c, "#94A3B8") for c in cat["Category"]],
                    line=dict(color="white", width=2)),
        texttemplate="%{label}<br>%{percent:.1%}",
        textposition="outside",
        hovertemplate="<b>%{label}</b><br>Sales: $%{value:,.2f}<br>"
                      "Kontribusi: %{percent:.1%}<extra></extra>",
    ))
    fig.update_layout(showlegend=False)
    return _layout(fig, 400)


def chart_tren(m: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=m["Tanggal"], y=m["Sales"], mode="lines+markers",
        line=dict(color=ROYAL, width=2.5, shape="spline", smoothing=0.6),
        marker=dict(size=7, color="white", line=dict(color=ROYAL, width=2)),
        customdata=m["Label"],
        hovertemplate="<b>%{customdata}</b><br>Sales: $%{y:,.2f}<extra></extra>",
    ))
    fig.update_xaxes(title=None, tickformat="%b %Y", gridcolor=GRID)
    fig.update_yaxes(title="Total Sales (USD)", tickprefix="$", tickformat=",",
                     gridcolor=GRID, zeroline=False, rangemode="tozero")
    return _layout(fig, 420)


# ---------------------------------------------------------------------------
# Tampilan (CSS & komponen)
# ---------------------------------------------------------------------------
CSS = f"""
<style>
.stApp {{ background: #F5F7FB; }}
.block-container {{ padding-top: 2rem; padding-bottom: 2rem; max-width: 1300px; }}
#MainMenu, footer {{ visibility: hidden; }}
section[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid {GRID}; }}

.hero {{
  background: linear-gradient(135deg, {NAVY} 0%, #14357F 100%);
  color: #fff; padding: 1.6rem 1.8rem; border-radius: 16px; margin-bottom: 1.2rem;
}}
.hero h1 {{ margin: 0; font-size: 1.9rem; font-weight: 700; color: #fff; padding: 0; }}
.hero p {{ margin: .4rem 0 0; color: #CBD5E1; font-size: 1rem; }}
.hero .periode {{ margin-top: .8rem; font-size: .85rem; color: #93C5FD; }}

.kpi {{
  background: #fff; border: 1px solid {GRID}; border-left: 5px solid {ROYAL};
  border-radius: 14px; padding: 1.1rem 1.3rem; height: 100%;
  box-shadow: 0 1px 3px rgba(15,23,42,.06);
}}
.kpi .label {{ color: {TEXT_MUTED}; font-size: .8rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: .05em; }}
.kpi .value {{ color: {NAVY}; font-size: 1.8rem; font-weight: 700; margin-top: .25rem; }}
.kpi .value.small {{ font-size: 1.05rem; line-height: 1.35; }}
.kpi .sub {{ color: {ROYAL}; font-size: 1.05rem; font-weight: 600; margin-top: .3rem; }}

.section-title {{ color: {NAVY}; font-size: 1.25rem; font-weight: 700; margin: 1.8rem 0 .2rem; }}
.section-desc {{ color: {TEXT_MUTED}; font-size: .9rem; margin-bottom: .6rem; }}
.card {{
  background: #fff; border: 1px solid {GRID}; border-radius: 14px;
  padding: 1rem 1.2rem; box-shadow: 0 1px 3px rgba(15,23,42,.06);
}}
.insight {{
  background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 12px;
  padding: .9rem 1.2rem; margin-top: .6rem; color: {NAVY};
}}
.insight-title {{ font-weight: 700; margin-bottom: .3rem; }}
.insight ul {{ margin: 0; padding-left: 1.2rem; }}
.insight li {{ margin: .25rem 0; }}
.footer {{ text-align: center; color: {TEXT_MUTED}; font-size: .8rem;
  margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid {GRID}; }}

@media (max-width: 768px) {{
  .hero h1 {{ font-size: 1.4rem; }}
  .kpi .value {{ font-size: 1.4rem; }}
  .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
}}
</style>
"""


def kpi_card(label: str, value: str, sub: str | None = None, small: bool = False) -> str:
    cls = "value small" if small else "value"
    sub_html = f'<div class="sub">{html.escape(sub)}</div>' if sub else ""
    return (f'<div class="kpi"><div class="label">{html.escape(label)}</div>'
            f'<div class="{cls}">{html.escape(value)}</div>{sub_html}</div>')


def section(title: str, desc: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div>'
                f'<div class="section-desc">{desc}</div>', unsafe_allow_html=True)


def insight_box(items: list[str], title: str = "Analisis Otomatis") -> None:
    # Teks di-escape lebih dulu (aman untuk nama produk), lalu **tebal** diubah ke <b>.
    def to_html(teks: str) -> str:
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(teks))

    li = "".join(f"<li>{to_html(t)}</li>" for t in items)
    st.markdown(
        f'<div class="insight"><div class="insight-title">💡 {title}</div>'
        f"<ul>{li}</ul></div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Filter (sidebar)
# ---------------------------------------------------------------------------
def init_filter_state(df: pd.DataFrame) -> dict:
    opsi = {
        "min_date": df["Order Date"].min().date(),
        "max_date": df["Order Date"].max().date(),
        "regions": sorted(df["Region"].dropna().unique()),
        "categories": sorted(df["Category"].dropna().unique()),
        "segments": sorted(df["Segment"].dropna().unique()),
    }
    defaults = {
        "f_date": (opsi["min_date"], opsi["max_date"]),
        "f_region": opsi["regions"],
        "f_category": opsi["categories"],
        "f_segment": opsi["segments"],
    }
    for key, val in defaults.items():
        st.session_state.setdefault(key, val)
    opsi["defaults"] = defaults
    return opsi


def reset_filters(defaults: dict) -> None:
    for key, val in defaults.items():
        st.session_state[key] = val


def render_sidebar(opsi: dict) -> tuple[date, date, list, list, list]:
    with st.sidebar:
        st.markdown(f"<h3 style='color:{NAVY};margin-top:0'>🔎 Filter Data</h3>",
                    unsafe_allow_html=True)
        st.date_input("Rentang Tanggal Pesanan", key="f_date",
                      min_value=opsi["min_date"], max_value=opsi["max_date"],
                      format="DD/MM/YYYY")
        st.multiselect("Region", opsi["regions"], key="f_region")
        st.multiselect("Kategori", opsi["categories"], key="f_category")
        st.multiselect("Segmen", opsi["segments"], key="f_segment")
        st.button("↺ Reset Filter", on_click=reset_filters,
                  args=(opsi["defaults"],), use_container_width=True)

    rentang = st.session_state["f_date"]
    if isinstance(rentang, (tuple, list)) and len(rentang) == 2:
        start, end = rentang
    elif isinstance(rentang, (tuple, list)) and len(rentang) == 1:
        start = end = rentang[0]   # pengguna baru memilih satu tanggal
    else:
        start = end = rentang
    return (start, end, st.session_state["f_region"],
            st.session_state["f_category"], st.session_state["f_segment"])


# ---------------------------------------------------------------------------
# Aplikasi utama
# ---------------------------------------------------------------------------
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    # --- Muat data dengan penanganan error ---
    if not CSV_PATH.exists():
        st.error(f"File data tidak ditemukan: `{CSV_PATH.name}`. "
                 f"Letakkan file tersebut di folder yang sama dengan `app.py`.")
        st.stop()
    try:
        df, n_duplikat = load_data(str(CSV_PATH))
    except ValueError as e:
        st.error(f"Format data tidak sesuai. {e}")
        st.stop()
    except Exception as e:  # file rusak, encoding, dll.
        st.error(f"Gagal membaca data: {e}")
        st.stop()

    if df.empty:
        st.error("Dataset kosong setelah pembersihan data.")
        st.stop()

    opsi = init_filter_state(df)
    start, end, regions, categories, segments = render_sidebar(opsi)

    # --- Header ---
    filtered = apply_filters(df, start, end, regions, categories, segments)
    periode_data = f"{tanggal_id(opsi['min_date'])} – {tanggal_id(opsi['max_date'])}"
    periode_aktif = f"{tanggal_id(start)} – {tanggal_id(end)}"
    st.markdown(
        f"""<div class="hero">
        <h1>Superstore Sales Dashboard</h1>
        <p>Dashboard Analisis Penjualan untuk Memahami Performa Produk, Kategori, dan Tren Penjualan.</p>
        <div class="periode">Periode data tersedia: {periode_data} &nbsp;•&nbsp;
        Periode dianalisis: {periode_aktif}</div></div>""",
        unsafe_allow_html=True,
    )

    # --- Validasi filter ---
    if not (regions and categories and segments):
        st.warning("Salah satu filter (Region, Kategori, atau Segmen) belum dipilih. "
                   "Pilih minimal satu nilai pada setiap filter, atau tekan **Reset Filter**.")
        st.stop()
    if start > end:
        st.warning("Tanggal awal lebih besar daripada tanggal akhir. Perbaiki rentang tanggal.")
        st.stop()
    if filtered.empty:
        st.warning("Tidak ada transaksi yang cocok dengan kombinasi filter saat ini. "
                   "Perluas rentang tanggal atau pilihan filter, atau tekan **Reset Filter**.")
        st.stop()

    # --- Agregasi (sekali per perubahan filter) ---
    total_sales = float(filtered["Sales"].sum())
    total_orders = int(filtered["Order ID"].nunique())
    prod = product_sales(filtered)
    cat = category_sales(filtered)
    mon = monthly_sales(filtered)

    # --- KPI ---
    k1, k2, k3 = st.columns(3)
    top = prod.iloc[0]
    k1.markdown(kpi_card("Produk Terlaris", top["Product Name"], usd(top["Sales"]), small=True),
                unsafe_allow_html=True)
    k2.markdown(kpi_card("Total Sales", usd(total_sales)), unsafe_allow_html=True)
    k3.markdown(kpi_card("Total Orders", angka(total_orders)), unsafe_allow_html=True)

    # --- Analisis 1 ---
    section("Analisis 1 — Produk dengan Penjualan Tertinggi",
            "10 produk dengan total nilai penjualan (SUM Sales) terbesar.")
    st.plotly_chart(chart_top_produk(prod), config={"displayModeBar": False})
    insight_box(insight_produk(prod, total_sales))

    # --- Analisis 2 ---
    section("Analisis 2 — Penjualan Berdasarkan Kategori Produk",
            "Kontribusi setiap kategori terhadap total penjualan.")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.plotly_chart(chart_kategori(cat), config={"displayModeBar": False})
    with c2:
        insight_box(insight_kategori(cat))

    # --- Analisis 3 ---
    section("Analisis 3 — Tren Penjualan Bulanan",
            "Total penjualan per bulan, diurutkan kronologis (tahun berbeda tidak digabung).")
    st.plotly_chart(chart_tren(mon), config={"displayModeBar": False})
    insight_box(insight_tren(mon))

    # --- Ringkasan ---
    section("Ringkasan Analisis Penjualan",
            "Kesimpulan dari ketiga analisis berdasarkan filter yang sedang aktif.")
    for baris in ringkasan(prod, cat, mon, total_sales, total_orders, len(prod)):
        st.markdown(baris)
    st.caption("Catatan: dataset tidak memiliki kolom Quantity maupun Profit, sehingga "
               "analisis jumlah unit terjual dan keuntungan tidak dapat dilakukan. "
               "Seluruh nilai dalam USD.")

    # --- Footer ---
    st.markdown(
        f'<div class="footer">Superstore Sales Dashboard • Sumber data: {CSV_PATH.name} • '
        f'{angka(len(df))} baris data ({angka(len(filtered))} baris sesuai filter) • '
        f'Duplikat dihapus: {angka(n_duplikat)} • Dibangun dengan Python, Streamlit, Pandas, dan Plotly</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
