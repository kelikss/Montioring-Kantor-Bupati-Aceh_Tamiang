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
    # Memberikan indikator warna pada deviasi kumulatif
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
st.subheader("🗺️ Peta Interaktif Penanganan Kawasan")

# Gandakan data spasial & bersihkan string spasi kosong
gdf_peta = GLOBAL_GDF.copy()
gdf_peta['ITEM'] = gdf_peta['ITEM'].astype(str).str.strip()
df_status_clean = df_rekap_raw.copy()
df_status_clean['ITEM'] = df_status_clean['ITEM'].astype(str).str.strip()

# Gabungkan kolom 'Status Pekerjaan' ke data spasial untuk pewarnaan poligon
gdf_peta = gdf_peta.merge(df_status_clean[['ITEM', 'Status Pekerjaan']], on='ITEM', how='left')

# Inisialisasi Basemaps kustom
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

# Centering peta ke wilayah Kantor Bupati Aceh Tamiang
m = folium.Map(location=[4.3000, 98.0453], zoom_start=17, tiles=None, control_scale=True)
for layer in basemaps.values():
    layer.add_to(m)

# Fungsi pewarnaan poligon peta berdasarkan status pekerjaan
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

# Render peta Folium ke dalam UI Streamlit
st_folium(m, width="100%", height=500, returned_objects=[])

st.markdown("---")

# ==============================================================================
# 6. KOMPONEN VISUAL 3: TABEL REKAPITULASI & GRAFIK PROGRESS (Side-by-Side)
# ==============================================================================
col_kiri, col_kanan = st.columns([1, 1])

with col_kiri:
    st.subheader("📋 Rekapitulasi Progress Kerja")
    
    # Format penamaan kolom tabel untuk User Interface
    df_tabel = df_rekap_raw.rename(
        columns={
            'ITEM': 'Penanganan',
            'RENCANA': 'Rencana (%)',
            'REALISASI': 'Realisasi (%)',
            'DEVIASI': 'Deviasi (%)'
        }
    )
    # Tampilkan tabel interaktif yang bisa di-sorting dengan style bawaan Streamlit
    st.dataframe(df_tabel, use_container_width=True, hide_index=False)

with col_kanan:
    st.subheader("📊 Grafik Perbandingan Progress (%)")
    
    # Transformasi data agar sesuai dengan struktur visualisasi grafik Streamlit
    df_chart = df_rekap_raw.melt(
        id_vars=['ITEM'], 
        value_vars=['RENCANA', 'REALISASI'], 
        var_name='Tipe Progres', 
        value_name='Persentase (%)'
    ).rename(columns={'ITEM': 'Item Pekerjaan'})
    
    # Membuat Bar Chart berdampingan (Grouped Bar Chart) secara native
    st.bar_chart(
        data=df_chart,
        x="Item Pekerjaan",
        y="Persentase (%)",
        color="Tipe Progres",
        use_container_width=True
    )