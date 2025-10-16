
import csv
import datetime
import math
import os
import requests
import pandas as pd
import plotly.express as px
from flask import Flask, render_template, request
from functools import lru_cache

app = Flask(__name__)

# Constants
SOLAR_CONSTANT = 1367  # W/m²
CSV_DIR = os.path.join(os.path.dirname(__file__), 'csv')
REGION_FILE = os.path.join(CSV_DIR, 'india_regions.csv')
USER_QUERIES_FILE = os.path.join(CSV_DIR, 'User_Query.csv')
TOP_REGIONS_FILE = os.path.join(CSV_DIR, 'TOP_10_REGIONS.csv')

# Ensure CSV directory exists
os.makedirs(CSV_DIR, exist_ok=True)

# Use a session to reuse TCP connections
session = requests.Session()
session.headers.update({"User-Agent": "SolarEnergyApp/1.0"})

# --- Helper Functions ---
def declination_angle(n):
    return 23.45 * math.sin(math.radians(360 * (284 + n) / 365))

def daylight_hours(latitude, decl):
    lat_rad = math.radians(latitude)
    decl_rad = math.radians(decl)
    try:
        ha = math.acos(-math.tan(lat_rad) * math.tan(decl_rad))
        return (2 * ha * 180 / math.pi) / 15
    except ValueError:
        return 0

def solar_intensity(cloud_cover):
    return round(SOLAR_CONSTANT * (1 - cloud_cover / 100), 2)

def calculate_energy(intensity, daylight):
    return round((intensity * daylight * 3600) / 1_000_000, 2)

# --- Cached API Calls ---
@lru_cache(maxsize=512)
def get_weather_data_cached(lat_rounded, lon_rounded):
    lat = lat_rounded
    lon = lon_rounded
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=cloudcover&current_weather=true"
    try:
        res = session.get(url, timeout=8)
        res.raise_for_status()
        data = res.json()
        temp = data.get("current_weather", {}).get("temperature", 25)
        clouds_list = data.get("hourly", {}).get("cloudcover", [0])
        # Use first hour or daily average
        clouds = sum(clouds_list)/len(clouds_list) if clouds_list else 0
        return temp, clouds
    except Exception:
        return 25, 0  # fallback

def get_weather_data(lat, lon):
    return get_weather_data_cached(round(lat, 4), round(lon, 4))

@lru_cache(maxsize=512)
def get_region_name_from_coords_cached(lat_rounded, lon_rounded):
    lat = lat_rounded
    lon = lon_rounded
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10"
        res = session.get(url, timeout=8)
        res.raise_for_status()
        data = res.json()
        addr = data.get("address", {})
        return addr.get("city") or addr.get("town") or addr.get("village") or addr.get("state") or "Unknown"
    except Exception:
        return "Unknown"

def get_region_name_from_coords(lat, lon):
    return get_region_name_from_coords_cached(round(lat, 4), round(lon, 4))

def read_regions(file_path):
    regions = []
    if os.path.exists(file_path):
        with open(file_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    regions.append({
                        "region": row["region"],
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"])
                    })
                except Exception:
                    continue
    return regions

def process_and_save_top_regions():
    today = datetime.date.today()
    now = datetime.datetime.now().strftime("%H:%M:%S")
    day_number = today.timetuple().tm_yday
    decl = declination_angle(day_number)

    regions = read_regions(REGION_FILE)
    results = []

    for r in regions:
        lat = r["latitude"]
        lon = r["longitude"]
        temp, clouds = get_weather_data(lat, lon)
        daylight = daylight_hours(lat, decl)
        intensity = solar_intensity(clouds)
        energy = calculate_energy(intensity, daylight)

        results.append({
            "region": r["region"],
            "date": str(today),
            "time": now,
            "temp": temp,
            "cloud": round(clouds, 2),
            "intensity": intensity,
            "daylight": round(daylight, 2),
            "energy": energy
        })

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by='energy', ascending=False).head(10)
        df.to_csv(TOP_REGIONS_FILE, index=False, encoding='utf-8')
    return df

def generate_graphs(df):
    graphs = {}

    # Correlation Heatmap
    corr_matrix = df[['temp', 'cloud', 'intensity', 'daylight', 'energy']].corr()
    fig_corr = px.imshow(corr_matrix, text_auto=True, color_continuous_scale='Viridis',
                         title="Correlation Between Solar Parameters")
    fig_corr.update_layout(width=700, height=600)
    graphs['Correlation Heatmap'] = fig_corr.to_html(full_html=False)

    # Energy by City
    fig_energy_city = px.bar(df, x='region', y='energy', text='energy', color='energy',
                             color_continuous_scale='Plasma', title="Top 10 Cities by Solar Energy Output")
    fig_energy_city.update_traces(marker_line_color='black', marker_line_width=1.5, textposition='outside')
    fig_energy_city.update_layout(width=800, height=500)
    graphs['Top Cities by Energy'] = fig_energy_city.to_html(full_html=False)

    # Energy vs Temperature
    fig_energy_temp = px.scatter(df, x='temp', y='energy', size='daylight', color='cloud',
                                 color_continuous_scale='Viridis', hover_name='region',
                                 title="Energy vs Temperature")
    fig_energy_temp.update_layout(width=800, height=500)
    graphs['Energy vs Temperature'] = fig_energy_temp.to_html(full_html=False)

    # Cloud Cover Effect
    fig_cloud_effect = px.line(df.sort_values('cloud'), x='cloud', y='energy', markers=True,
                               title="Cloud Cover Effect on Energy")
    fig_cloud_effect.update_layout(width=800, height=500)
    graphs['Cloud Cover Effect'] = fig_cloud_effect.to_html(full_html=False)

    # Daylight vs Energy
    fig_daylight_energy = px.scatter(df, x='daylight',
                                    y='energy',
                                    size='temp',
                                    color='intensity',
                                    color_continuous_scale='Cividis',
                                    hover_name='region',
                                    title="Daylight vs Energy")
    fig_daylight_energy.update_layout(width=800, height=500)
    graphs['Daylight vs Energy'] = fig_daylight_energy.to_html(full_html=False)

    return graphs

# --- Flask Route ---
@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    top_regions_df = None
    graphs = {}

    if request.method == "POST":
        lat_str = request.form.get("latitude", "").strip()
        lon_str = request.form.get("longitude", "").strip()
        try:
            latitude = float(lat_str) if lat_str else None
            longitude = float(lon_str) if lon_str else None
        except ValueError:
            latitude = None
            longitude = None

        if latitude is None or longitude is None:
            result = {"error": "Please allow location access or enter latitude/longitude."}
        else:
            region = request.form.get("region")
            if not region or region.strip() == "":
                region = get_region_name_from_coords(latitude, longitude)

            today = datetime.date.today()
            n = today.timetuple().tm_yday
            decl = declination_angle(n)
            daylight = daylight_hours(latitude, decl)
            temp, cloud_cover = get_weather_data(latitude, longitude)
            intensity = solar_intensity(cloud_cover)
            energy_output = calculate_energy(intensity, daylight)

            result = {
                "region": region,
                "date": today,
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "temp": temp,
                "cloud": round(cloud_cover, 2),
                "intensity": intensity,
                "daylight": round(daylight, 2),
                "energy": energy_output
            }

            # Save user query
            write_header = not os.path.exists(USER_QUERIES_FILE)
            with open(USER_QUERIES_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=result.keys())
                if write_header:
                    writer.writeheader()
                writer.writerow(result)

            # Top 10 regions
            top_regions_df = process_and_save_top_regions()
            if top_regions_df is not None and not top_regions_df.empty:
                graphs = generate_graphs(top_regions_df)

    return render_template("index.html",
                           result=result,
                           top_regions=top_regions_df.to_html(classes="table-auto border border-gray-300 rounded-lg text-center") if top_regions_df is not None else "",
                           graphs=graphs)

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=False)