import os
import geopandas as gpd
import pandas as pd
import folium
import numpy as np
import streamlit as st
from streamlit_folium import st_folium

# ==============================================================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Monitoring Penanganan Kawasan Kantor Bupati Aceh Tamiang",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------------------------
# KUSTOMISASI UKURAN HURUF (CSS INJECTION)
# ------------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Mengecilkan ukuran Judul Utama dan Keterangan */
    h1 {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
    .stCaption {
        font-size: 0.85rem !important;
    }
    
    /* Mengecilkan ukuran Sub-header (Subjudul bagian) */
    h3 {
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        margin-top: 10px !important;
    }
    
    /* Mengecilkan komponen teks pada Kartu Metrik (Label & Angka) */
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.8rem !important;
    }
    
    /* Mengecilkan ukuran huruf di dalam tabel data (st.dataframe) */
    div[data-testid="stDataFrame"] table {
        font-size: 0.8rem !important;
    }
    div[data-testid="stDataFrame"] td, th {
        padding: 4px 8px !important;
    }
    /* =========================================================================
       PENGATURAN METRIK: Mengecilkan huruf & merapatkan spasi huruf-angka
       ========================================================================= */
    /* 1. Mengatur label metrik (huruf) */
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        margin-bottom: -10px !important; /* Menarik angka di bawahnya agar lebih rapat */
    }
    
    /* 2. Mengatur wadah nilai metrik (angka) */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        line-height: 1.1 !important;     /* Merapatkan ruang vertikal teks angka */
        padding-top: 0px !important;     /* Menghilangkan spasi kosong di atas angka */
        margin-top: 0px !important;
    }
    
    /* 3. Mengatur jarak delta (indikator persen kecil di bawah angka jika ada) */
    [data-testid="stMetricDelta"] {
        font-size: 0.8rem !important;
        margin-top: -4px !important;     /* Menarik indikator delta ke atas agar rapat dengan angka */
    }
    
    /* Mengecilkan ukuran huruf di dalam tabel data (st.dataframe) */
    div[data-testid="stDataFrame"] table {
        font-size: 0.8rem !important;
    }
    div[data-testid="stDataFrame"] td, th {
        padding: 4px 8px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Title & Subtitle Dashboard
st.title("MONITORING PENANGANAN KAWASAN KANTOR BUPATI ACEH TAMIANG")
st.caption("Konsultan MK - Penanganan Pasca Bencana Aceh")
st.markdown("---")

# Path relatif file GeoJSON
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEOJSON_PATH = os.path.join(BASE_DIR, "PENANGANAN_KANTOR_BUPATI.geojson")

# ==============================================================================
# 2. OPTIMALISASI: Membaca GeoJSON menggunakan Cache Streamlit
# ==============================================================================
@st.cache_data
def muat_data_geojson(path):
    if os.path.exists(path):
        return gpd.read_file(path)
    else:
        st.error(f"❌ File tidak ditemukan di: {path}. Tolong periksa nama file atau lokasi folder di GitHub Anda.")
        st.stop()

GLOBAL_GDF = muat_data_geojson(GEOJSON_PATH)

# ==============================================================================
# 3. HELPER: Fungsi Kalkulasi Rekapitulasi Progres & Status
# ==============================================================================
def hitung_rekap_dan_status(gdf_input):
    # Proses rekapitulasi data per Item
    df_rekap = gdf_input.groupby('ITEM')[['RENCANA', 'REALISASI', 'DEVIASI']].sum().reset_index()
    
    # Tentukan Kondisi Logika Klasifikasi Progres
    kondisi = [
        (df_rekap["DEVIASI"] > 0),   # Cepat
        (df_rekap["DEVIASI"] == 0),  # Tepat Waktu
        (df_rekap["DEVIASI"] < 0)    # Terlambat
    ]
    label = ["Cepat (Ahead)", "Tepat Waktu", "Terlambat (Behind)"]
    df_rekap["Status Pekerjaan"] = np.select(kondisi, label, default="Tidak Diketahui")
    
    return df_rekap

# Proses kalkulasi awal data rekap
df_rekap_raw = hitung_rekap_dan_status(GLOBAL_GDF)

# ==============================================================================
# 4. KOMPONEN VISUAL 1: KARTU METRIK TOTAL UTAMA
# ==============================================================================
total_rencana = df_rekap_raw['RENCANA'].sum() / 5
total_realisasi = df_rekap_raw['REALISASI'].sum() / 5
total_deviasi = total_realisasi - total_rencana

col_metric1, col_metric2, col_metric3 = st.columns(3)

with col_metric1:
    st.metric(label="📊 TOTAL RENCANA", value=f"{total_rencana:,.2f} %")

with col_metric2:
    st.metric(label="✅ TOTAL REALISASI", value=f"{total_realisasi:,.2f} %")

with col_metric3:
    st.metric(
        label="📉 DEVIASI KUMULATIF", 
        value=f"{total_deviasi:,.2f} %", 
        delta=f"{total_deviasi:,.2f} %",
        delta_color="normal" if total_deviasi >= 0 else "inverse"
    )

st.markdown("###")

# ==============================================================================
# 5. KOMPONEN VISUAL 2: PETA INTERAKTIF FOLIUM
# ==============================================================================
st.subheader("🗺️ Peta Interaktif Penanganan Kawasan Kantor Bupati Aceh Tamiang")

gdf_peta = GLOBAL_GDF.copy()
gdf_peta['ITEM'] = gdf_peta['ITEM'].astype(str).str.strip()
df_status_clean = df_rekap_raw.copy()
df_status_clean['ITEM'] = df_status_clean['ITEM'].astype(str).str.strip()

gdf_peta = gdf_peta.merge(df_status_clean[['ITEM', 'Status Pekerjaan']], on='ITEM', how='left')

basemaps = {
    'OpenStreetMap': folium.TileLayer('openstreetmap', name='OpenStreetMap'),
    'Google Maps': folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        attr='Google', name='Google Maps'
    ),
    'Google Satellite': folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google', name='Google Satellite'
    ),
    'Google Hybrid': folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google', name='Google Hybrid'
    )
}

m = folium.Map(location=[4.3000, 98.0453], zoom_start=17, tiles=None, control_scale=True)
for layer in basemaps.values():
    layer.add_to(m)

def penentu_warna(feature):
    status = feature['properties'].get('Status Pekerjaan', '')
    if not status or pd.isna(status):
        status = "Tidak Diketahui"
    
    status_lower = str(status).lower()
    if "cepat" in status_lower or "ahead" in status_lower:
        return {'fillColor': '#28a745', 'color': '#1e7e34', 'fillOpacity': 0.6, 'weight': 2.5}
    elif "tepat" in status_lower:
        return {'fillColor': '#ffc107', 'color': '#d39e00', 'fillOpacity': 0.6, 'weight': 2.5}
    elif "terlambat" in status_lower or "behind" in status_lower:
        return {'fillColor': '#dc3545', 'color': '#bd2130', 'fillOpacity': 0.6, 'weight': 2.5}
    else:
        return {'fillColor': '#6c757d', 'color': '#495057', 'fillOpacity': 0.5, 'weight': 1.5}

folium.GeoJson(
    gdf_peta,
    name="Kawasan Penanganan",
    style_function=penentu_warna,
    tooltip=folium.GeoJsonTooltip(
        fields=['KODE', 'ITEM', 'RENCANA', 'REALISASI', 'DEVIASI', 'Status Pekerjaan'],
        aliases=['Kode:', 'Penanganan:', 'Rencana (%):', 'Realisasi (%):', 'Deviasi (%):', 'Status Progres:']
    )
).add_to(m)

folium.LayerControl().add_to(m)

st_folium(m, width="100%", height=500, returned_objects=[])

st.markdown("---")

# ==============================================================================
# 6. KOMPONEN VISUAL 3: TABEL REKAPITULASI & GRAFIK PROGRESS (Side-by-Side)
# ==============================================================================
col_kiri, col_kanan = st.columns([1, 1])

with col_kiri:
    st.subheader("📋 Rekapitulasi Progress Kerja")
    
    df_tabel = df_rekap_raw.rename(
        columns={
            'ITEM': 'Penanganan',
            'RENCANA': 'Rencana (%)',
            'REALISASI': 'Realisasi (%)',
            'DEVIASI': 'Deviasi (%)'
        }
    )
    st.dataframe(df_tabel, use_container_width=True, hide_index=False)

with col_kanan:
    st.subheader("📊 Grafik Perbandingan Progress (%)")
    
    df_chart = df_rekap_raw.melt(
        id_vars=['ITEM'], 
        value_vars=['RENCANA', 'REALISASI'], 
        var_name='Tipe Progres', 
        value_name='Persentase (%)'
    ).rename(columns={'ITEM': 'Item Pekerjaan'})
    
    st.bar_chart(
        data=df_chart,
        x="Item Pekerjaan",
        y="Persentase (%)",
        color="Tipe Progres",
        use_container_width=True
    )