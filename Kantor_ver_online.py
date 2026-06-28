import os
import geopandas as gpd
import pandas as pd
import folium
import numpy as np
import streamlit as st
from streamlit_folium import st_folium
from branca.element import MacroElement
from jinja2 import Template

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
    h1 {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
    .stCaption {
        font-size: 0.85rem !important;
    }
    h3 {
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        margin-top: 10px !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
    }
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

st.title("MONITORING PENANGANAN KAWASAN KANTOR BUPATI ACEH TAMIANG")
st.caption("Konsultan MK - Penanganan Pasca Bencana Aceh")
st.markdown("---")

# Path File Spasial & Tabular
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEOJSON_PATH = os.path.join(BASE_DIR, "PENANGANAN_KANTOR_BUPATI.geojson")
DATA_CFV_PATH = os.path.join(BASE_DIR, "DATA_PROGRESS.csv") 

# ==============================================================================
# 2. CACHING DATA: Membaca GeoJSON & Data Tabular CFV
# ==============================================================================
@st.cache_data
def muat_data_spasial(path):
    if os.path.exists(path):
        gdf = gpd.read_file(path)
        if 'KODE' in gdf.columns:
            gdf['KODE'] = gdf['KODE'].astype(str).str.strip()
        if 'ITEM' in gdf.columns:
            gdf['ITEM'] = gdf['ITEM'].astype(str).str.strip()
        return gdf
    else:
        st.error(f"❌ File GeoJSON tidak ditemukan di: {path}.")
        st.stop()

@st.cache_data
def muat_data_tabular(path):
    if os.path.exists(path):
        df = pd.read_csv(path)
        if 'KODE' in df.columns:
            df['KODE'] = df['KODE'].astype(str).str.strip()
        if 'ITEM' in df.columns:
            df['ITEM'] = df['ITEM'].astype(str).str.strip()
        return df
    else:
        st.warning(f"⚠️ File data tabular ({os.path.basename(path)}) tidak ditemukan. Membuat data simulasi sementara...")
        data_simulasi = {
            'KODE': ['K01', 'K02', 'K03'],
            'ITEM': ['Pekerjaan Struktur', 'Pekerjaan Arsitektur', 'Pekerjaan Lansekap'],
            'REALISASI': [42.5, 28.0, 30.0]
        }
        return pd.DataFrame(data_simulasi)

# Memuat data asli/simulasi
SPASIAL_GDF = muat_data_spasial(GEOJSON_PATH)
TABULAR_DF = muat_data_tabular(DATA_CFV_PATH)

# ==============================================================================
# 3. PENGGABUNGAN DATA (MERGE) & KLASIFIKASI KATEGORI REALISASI
# ==============================================================================
# Menentukan label visualisasi peta berdasarkan capaian progress realisasi saat ini
kondisi = [
    (TABULAR_DF["REALISASI"] >= 75.0),
    (TABULAR_DF["REALISASI"] >= 40.0) & (TABULAR_DF["REALISASI"] < 75.0),
    (TABULAR_DF["REALISASI"] > 0) & (TABULAR_DF["REALISASI"] < 40.0)
]
label = ["Progres Tinggi (>=75%)", "Progres Sedang (40-74%)", "Progres Rendah (<40%)"]
TABULAR_DF["Status Pekerjaan"] = np.select(kondisi, label, default="Belum Dimulai / Selesai")

# Gabungkan data atribut spasial GeoJSON dengan Data Tabular Progres
kolom_kunci = 'KODE' if 'KODE' in SPASIAL_GDF.columns and 'KODE' in TABULAR_DF.columns else 'ITEM'

GLOBAL_GDF = SPASIAL_GDF.merge(TABULAR_DF, on=kolom_kunci, how='inner', suffixes=('', '_drop'))
GLOBAL_GDF = GLOBAL_GDF.loc[:, ~GLOBAL_GDF.columns.str.endswith('_drop')]

# Hitung ringkasan data untuk rekapitulasi tabel dan grafik
df_rekap_raw = GLOBAL_GDF.groupby('ITEM')[['REALISASI']].sum().reset_index()
df_rekap_raw = df_rekap_raw.merge(TABULAR_DF[['ITEM', 'Status Pekerjaan']].drop_duplicates(), on='ITEM', how='left')

# ==============================================================================
# 4. KOMPONEN VISUAL 1: KARTU METRIK TOTAL REALISASI UTAMA
# ==============================================================================
total_realisasi = TABULAR_DF['REALISASI'].mean()  # Menggunakan rata-rata capaian kumulatif fisik kawasan

col_metric1, col_metric2 = st.columns([1, 2])

with col_metric1:
    st.metric(label="✅ RATA-RATA REALISASI FISIK KAWASAN", value=f"{total_realisasi:,.2f} %")

st.markdown("###")

# ==============================================================================
# 5. KUSTOM ELEMEN: MEMBUAT KOTAK LEGENDA CAPAIAN (HTML & JINJA2 TEMPLATE)
# ==============================================================================
class LegendaStatusProgres(MacroElement):
    def __init__(self, title):
        super(LegendaStatusProgres, self).__init__()
        self._template = Template("""
            {% macro html(this, kwargs) %}
            <div id='maplegend' class='maplegend' 
                style='position: absolute; z-index:9999; border: 2px solid grey; background-color:rgba(255, 255, 255, 0.9);
                border-radius:6px; padding: 10px; font-size:12px; font-family: sans-serif; right: 20px; bottom: 20px;'>
                
                <div class='legend-title' style='font-weight: bold; margin-bottom: 5px;'>{{this.title}}</div>
                <div class='legend-scale'>
                  <ul class='legend-labels' style='list-style: none; padding: 0; margin: 0;'>
                    <li style='margin-bottom: 3px;'><span style='display: inline-block; width: 25px; height: 15px; background:#28a745; opacity: 0.75; margin-right: 5px; border: 1px solid #1e7e34;'></span>Progres Tinggi (>=75%)</li>
                    <li style='margin-bottom: 3px;'><span style='display: inline-block; width: 25px; height: 15px; background:#ffc107; opacity: 0.75; margin-right: 5px; border: 1px solid #d39e00;'></span>Progres Sedang (40-74%)</li>
                    <li style='margin-bottom: 3px;'><span style='display: inline-block; width: 25px; height: 15px; background:#dc3545; opacity: 0.75; margin-right: 5px; border: 1px solid #bd2130;'></span>Progres Rendah (<40%)</li>
                    <li><span style='display: inline-block; width: 25px; height: 15px; background:#6c757d; opacity: 0.5; margin-right: 5px; border: 1px solid #495057;'></span>Belum Dimulai / Selesai</li>
                  </ul>
                </div>
            </div>
            {% endmacro %}
        """)
        self.title = title

# ==============================================================================
# 6. KOMPONEN VISUAL 2: PETA INTERAKTIF FOLIUM
# ==============================================================================
st.subheader("🗺️ Peta Interaktif Penanganan Kawasan Kantor Bupati Aceh Tamiang")

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
        status = "Belum Dimulai / Selesai"
    
    status_lower = str(status).lower()
    if "tinggi" in status_lower:
        return {'fillColor': '#28a745', 'color': '#1e7e34', 'fillOpacity': 0.6, 'weight': 2.5}
    elif "sedang" in status_lower:
        return {'fillColor': '#ffc107', 'color': '#d39e00', 'fillOpacity': 0.6, 'weight': 2.5}
    elif "rendah" in status_lower:
        return {'fillColor': '#dc3545', 'color': '#bd2130', 'fillOpacity': 0.6, 'weight': 2.5}
    else:
        return {'fillColor': '#6c757d', 'color': '#495057', 'fillOpacity': 0.5, 'weight': 1.5}

folium.GeoJson(
    GLOBAL_GDF,
    name="Kawasan Penanganan",
    style_function=penentu_warna,
    tooltip=folium.GeoJsonTooltip(
        fields=['KODE', 'ITEM', 'REALISASI', 'Status Pekerjaan'],
        aliases=['Kode:', 'Penanganan:', 'Realisasi (%):', 'Kategori Capaian:']
    )
).add_to(m)

m.add_child(LegendaStatusProgres(title="Kategori Realisasi Fisik"))
folium.LayerControl().add_to(m)

st_folium(m, width="100%", height=500, returned_objects=[])

st.markdown("---")

# ==============================================================================
# 7. KOMPONEN VISUAL 3: TABEL REKAPITULASI & GRAFIK PROGRESS (Side-by-Side)
# ==============================================================================
col_kiri, col_kanan = st.columns([1, 1])

with col_kiri:
    st.subheader("📋 Rekapitulasi Realisasi Kerja")
    
    df_tabel = df_rekap_raw.rename(
        columns={
            'ITEM': 'Penanganan',
            'REALISASI': 'Realisasi (%)',
            'Status Pekerjaan': 'Kategori Capaian'
        }
    )
    st.dataframe(df_tabel, use_container_width=True, hide_index=False)

with col_kanan:
    st.subheader("📊 Grafik Progress Realisasi (%)")
    
    st.bar_chart(
        data=df_rekap_raw,
        x="ITEM",
        y="REALISASI",
        use_container_width=True
    )