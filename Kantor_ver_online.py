import os
import geopandas as gpd
import pandas as pd
import folium
import numpy as np
import json
from flask import Flask, render_template_string

# 1. Inisialisasi Flask
app = Flask(__name__)

# Path relatif agar fleksibel saat dipindah ke server online
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEOJSON_PATH = os.path.join(BASE_DIR, "data", "PENANGANAN_KANTOR_BUPATI.geojson")

# ==============================================================================
# OPTIMALISASI: Membaca GeoJSON satu kali saja di awal agar Flask tidak macet
# ==============================================================================
if os.path.exists(GEOJSON_PATH):
    print("--- Memuat data GeoJSON ke memori, mohon tunggu... ---")
    GLOBAL_GDF = gpd.read_file(GEOJSON_PATH)
    print("--- Data GeoJSON berhasil dimuat dengan aman! ---")
else:
    raise FileNotFoundError(f"File tidak ditemukan di: {GEOJSON_PATH}. Tolong periksa nama atau lokasi folder Anda.")


# ==============================================================================
# HELPER: Fungsi standardisasi kalkulasi status agar sinkron di semua route
# ==============================================================================
def hitung_rekap_dan_status(gdf_input):
    # Proses rekapitulasi data per Item menggunakan nama kolom asli dari GeoJSON
    df_rekap = gdf_input.groupby('ITEM')[['RENCANA', 'REALISASI', 'DEVIASI']].sum().reset_index()
    
    # Tentukan Kondisi Logika Klasifikasi
    kondisi = [
        (df_rekap["DEVIASI"] > 0),  # Cepat
        (df_rekap["DEVIASI"] == 0), # Tepat Waktu
        (df_rekap["DEVIASI"] < 0)   # Terlambat
    ]
    label = ["Cepat (Ahead)", "Tepat Waktu", "Terlambat (Behind)"]
    df_rekap["Status Pekerjaan"] = np.select(kondisi, label, default="Tidak Diketahui")
    
    return df_rekap


# ==============================================================================
# ROUTE 1: KHUSUS MERENDER PETA (Dengan Pewarnaan Berdasarkan Status)
# ==============================================================================
@app.route('/peta_folium')
def peta_folium():
    gdf = GLOBAL_GDF.copy()
    
    # 1. Hitung status menggunakan fungsi helper
    df_status = hitung_rekap_dan_status(gdf)
    
    # Normalisasi teks untuk menghindari isu spasi tak terlihat saat merge
    gdf['ITEM'] = gdf['ITEM'].astype(str).str.strip()
    df_status['ITEM'] = df_status['ITEM'].astype(str).str.strip()
    
    # 2. Gabungkan (Merge) kolom 'Status Pekerjaan' kembali ke GeoDataFrame
    gdf = gdf.merge(df_status[['ITEM', 'Status Pekerjaan']], on='ITEM', how='left')
    
    # Definisi Pilihan Kustom Basemap (OpenStreetMap Standard ditaruh paling atas agar otomatis default)
    basemaps = {
        'OpenStreetMap Standard': folium.TileLayer(
            tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            attr='&copy; OpenStreetMap contributors',
            name='OpenStreetMap',
            overlay=False,
            control=True
        ),
        'Google Maps': folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Maps',
            overlay=False,
            control=True
        ),
        'Google Satellite': folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Satellite',
            overlay=False,
            control=True
        ),
        'Google Satellite Hybrid': folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Satellite Hybrid',
            overlay=False,
            control=True
        ),
    }
    
    # Inisiasi Peta (Centering ke wilayah Aceh Tamiang)
    m = folium.Map(location=[4.3000, 98.0453], zoom_start=17, tiles=None, control_scale=True)
    
    # Memasukkan Semua Pilihan Basemap ke Dalam Map
    for name, tilelyr in basemaps.items():
        tilelyr.add_to(m)

    # 3. Fungsi menentukan gaya & warna poligon berdasarkan nilai 'Status Pekerjaan'
    def penentu_warna(feature):
        status = feature['properties'].get('Status Pekerjaan', '')
        if not status or pd.isna(status):
            status = "Tidak Diketahui"
            
        status_lower = str(status).lower()
        
        if "cepat" in status_lower or "ahead" in status_lower:
            return {'fillColor': '#28a745', 'color': '#1e7e34', 'fillOpacity': 0.6, 'weight': 2.5} # Hijau
        elif "tepat" in status_lower:
            return {'fillColor': '#ffc107', 'color': '#d39e00', 'fillOpacity': 0.6, 'weight': 2.5} # Kuning
        elif "terlambat" in status_lower or "behind" in status_lower:
            return {'fillColor': '#dc3545', 'color': '#bd2130', 'fillOpacity': 0.6, 'weight': 2.5} # Merah
        else:
            return {'fillColor': '#6c757d', 'color': '#495057', 'fillOpacity': 0.5, 'weight': 1.5} # Abu-abu Fallback

    # Menambahkan Data GeoJSON ke Peta dengan mengaktifkan style_function kustom
    folium.GeoJson(
        gdf,
        name="Kawasan",
        style_function=penentu_warna,
        tooltip=folium.GeoJsonTooltip(
            fields=['KODE', 'ITEM', 'RENCANA', 'REALISASI', 'DEVIASI', 'Status Pekerjaan'],
            aliases=['Kode:', 'Penanganan:', 'Rencana (%):', 'Realisasi (%):', 'Deviasi (%):', 'Status Progres:']
        )
    ).add_to(m)
    
    # Tambahkan kontrol layer di pojok kanan atas
    folium.LayerControl().add_to(m)
    
    return m._repr_html_()


# ==============================================================================
# ROUTE 2: DASHBOARD UTAMA
# ==============================================================================
@app.route('/')
def index():
    gdf = GLOBAL_GDF.copy()

    # Hitung data rekap mentah menggunakan fungsi helper
    df_rekap_raw = hitung_rekap_dan_status(gdf)
    
    # Ubah nama kolom agar tampilan representasi Tabel HTML seragam di web
    df_rekap = df_rekap_raw.rename(
        columns={
            'ITEM': 'Penanganan',
            'RENCANA': 'Rencana (%)',
            'REALISASI': 'Realisasi (%)',
            'DEVIASI': 'Deviasi (%)'
        }
    )
    
    # DATA UNTUK CHART JAVASCRIPT
    list_penanganan = df_rekap['Penanganan'].tolist()
    list_rencana = df_rekap['Rencana (%)'].tolist()
    list_realisasi = df_rekap['Realisasi (%)'].tolist()
    
    # Hitung total keseluruhan angka mentah dibagi pembagi pembobotan (5)
    total_rencana = df_rekap['Rencana (%)'].sum() / 5
    total_realisasi = df_rekap['Realisasi (%)'].sum() / 5
    
    # Sinkronisasi format angka variabel ke ribuan dan desimal
    total_rencana_formatted = "{:,.2f}".format(total_rencana)
    total_realisasi_formatted = "{:,.2f}".format(total_realisasi)
    
    # Ubah dataframe menjadi tabel HTML Bootstrap
    tabel_html = df_rekap.to_html(classes='table table-striped table-bordered table-hover m-0', index=False)
    
    # Layout Tampilan Dashboard Utama dengan Multi-Bar Chart & Format Cetak
    html_layout = """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Monitoring Penanganan Kawasan Kantor Bupati Aceh Tamiang</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { padding: 25px; background-color: #f8f9fa; font-family: sans-serif; }
            .header-title { text-align: center; margin-bottom: 25px; border-bottom: 2px solid #343a40; padding-bottom: 10px; }
            .map-container { height: 550px; width: 100%; border: 2px solid #dee2e6; border-radius: 8px; overflow: hidden; margin-bottom: 30px; }
            .card-custom { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 25px; }
            thead th { background-color: #343a40 !important; color: white !important; text-align: center; }
            
            /* CSS Format Cetak Standar */
            @media print {
                body { background-color: #ffffff; padding: 0; }
                .no-print { display: none !important; }
                .map-container { display: none !important; } 
                .card-custom { box-shadow: none; padding: 0; margin-bottom: 20px; }
                .col-lg-6 { width: 50% !important; float: left; }
                .row { display: block; }
            }
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <div class="header-title">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <div style="width: 150px;"></div> 
                    <h3 class="m-0">MONITORING PENANGANAN KAWASAN KANTOR BUPATI ACEH TAMIANG</h3>
                    <button class="btn btn-dark no-print" onclick="window.print()">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-printer-fill me-2" viewBox="0 0 16 16">
                            <path d="M5 1a2 2 0 0 0-2 2v2H2a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h1v1a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-1h1a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-1V3a2 2 0 0 0-2-2zm4 4H7V2h2zm2 5H5V5h6zm-7 1h8v1H4z"/>
                        </svg> Cetak Laporan
                    </button>
                </div>
                <p class="text-muted">Konsultan MK - Penanganan Pasca Bencana Aceh</p>
            </div>
            
            <div class="row map-container">
                <div class="col-12">
                    <iframe src="/peta_folium" style="width: 100%; height: 100%; border: none;"></iframe>
                </div>
            </div>

            <div class="row">
                <div class="col-lg-6">
                    <div class="card-custom">
                        <h4 class="mb-3 text-secondary border-bottom pb-2">Rekapitulasi Progress Kerja</h4>
                        <div class="table-responsive">
                            {{ tabel_html | safe }}
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-6">
                    <div class="card-custom">
                        <h4 class="mb-3 text-secondary border-bottom pb-2">Grafik Perbandingan Progress (%)</h4>
                        <div style="position: relative; height:340px; width:100%">
                            <canvas id="progressChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row mt-2">
                <div class="col-md-6 mb-3">
                    <div class="p-4 bg-primary text-white rounded shadow-sm">
                        <h6 class="text-uppercase fw-semibold opacity-75">Total Rencana</h6>
                        <h2 class="mb-0 fw-bold">{{ total_rencana_txt }} %</h2>
                    </div>
                </div>
                <div class="col-md-6 mb-3">
                    <div class="p-4 bg-success text-white rounded shadow-sm">
                        <h6 class="text-uppercase fw-semibold opacity-75">Total Realisasi</h6>
                        <h2 class="mb-0 fw-bold">{{ total_realisasi_txt }} %</h2>
                    </div>
                </div>
            </div>
        </div>

        <script>
            const labelsData = {{ chart_labels | tojson }};
            const rencanaData = {{ chart_rencana | tojson }};
            const realisasiData = {{ chart_realisasi | tojson }};

            const ctx = document.getElementById('progressChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labelsData,
                    datasets: [
                        {
                            label: 'Rencana (%)',
                            data: rencanaData,
                            backgroundColor: 'rgba(54, 162, 235, 0.7)', 
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        },
                        {
                            label: 'Realisasi (%)',
                            data: realisasiData,
                            backgroundColor: 'rgba(40, 167, 69, 0.7)', 
                            borderColor: 'rgba(40, 167, 69, 1)',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, title: { display: true, text: 'Persentase (%)' } },
                        x: { ticks: { maxRotation: 15, minRotation: 0 } }
                    },
                    plugins: { legend: { display: true, position: 'top' } }
                }
            });
        </script>
    </body>
    </html>
    """
    
    return render_template_string(
        html_layout, 
        tabel_html=tabel_html, 
        total_rencana_txt=total_rencana_formatted, 
        total_realisasi_txt=total_realisasi_formatted,
        chart_labels=list_penanganan,
        chart_rencana=list_rencana,       
        chart_realisasi=list_realisasi     
    )


# 3. Jalankan Aplikasi pada Port 5001
if __name__ == '__main__':
    app.run(debug=True, port=5001, use_reloader=False, threaded=True)