# ☀️ Solar System Energy Calculator

A Flask web application that calculates and visualizes solar energy potential based on geographic location and current weather data. It provides solar intensity, daylight hours, and estimated solar energy output for user-input locations or predefined Indian regions.

---

## 🌍 Features

- 📍 Accepts user location via form input (latitude & longitude).
- ☁️ Fetches real-time cloud cover and temperature data using **Open-Meteo API**.
- ☀️ Calculates solar intensity, daylight hours, and energy output.
- 📊 Ranks top 10 regions in India with the highest solar energy potential.
- 📈 Visualizes data using **Plotly** interactive graphs.
- 📁 Saves user queries and top region data as CSV files.

---

## 🛠️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/solar-energy-calculator.git
cd solar-energy-calculator
