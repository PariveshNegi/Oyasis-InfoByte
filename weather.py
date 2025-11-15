import tkinter as tk
from tkinter import ttk, messagebox
import requests
from geopy.geocoders import Nominatim
from datetime import datetime, timedelta
import math
import threading

# Optional plotting
try:
    import matplotlib
    matplotlib.use("Agg")  # fallback for safety; we'll use FigureCanvasTkAgg if available
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import numpy as np
    HAVE_MPL = True
except Exception:
    HAVE_MPL = False

# --- Constants / Utilities ---
GEOCODER_USER_AGENT = "weather_gui_app_v1"
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"

# Mapping Open-Meteo weathercode -> (emoji, text)
WEATHERCODE_MAP = {
    0: ("☀️", "Clear sky"),
    1: ("🌤️", "Mainly clear"),
    2: ("⛅", "Partly cloudy"),
    3: ("☁️", "Overcast"),
    45: ("🌫️", "Fog"),
    48: ("🌫️", "Depositing rime fog"),
    51: ("🌦️", "Light drizzle"),
    53: ("🌧️", "Moderate drizzle"),
    55: ("🌧️", "Dense drizzle"),
    56: ("🌧️❄️", "Freezing drizzle"),
    57: ("🌧️❄️", "Dense freezing drizzle"),
    61: ("🌦️", "Slight rain"),
    63: ("🌧️", "Moderate rain"),
    65: ("🌧️", "Heavy rain"),
    66: ("🌧️❄️", "Freezing rain"),
    67: ("🌧️❄️", "Heavy freezing rain"),
    71: ("🌨️", "Light snow"),
    73: ("🌨️", "Moderate snow"),
    75: ("🌨️", "Heavy snow"),
    77: ("🌨️", "Snow grains"),
    80: ("🌦️", "Slight rain showers"),
    81: ("🌧️", "Moderate rain showers"),
    82: ("⛈️", "Violent rain showers"),
    85: ("🌨️", "Slight snow showers"),
    86: ("🌨️", "Heavy snow showers"),
    95: ("⛈️", "Thunderstorm"),
    96: ("⛈️", "Thunderstorm with slight hail"),
    99: ("⛈️", "Thunderstorm with heavy hail"),
}

def map_weathercode(code):
    return WEATHERCODE_MAP.get(code, ("❓", "Unknown"))

def c_to_f(c): return (c * 9/5) + 32
def f_to_c(f): return (f - 32) * 5/9

# --- Networking (geocoding + weather) ---
def geocode_location(location):
    geolocator = Nominatim(user_agent=GEOCODER_USER_AGENT, timeout=10)
    try:
        res = geolocator.geocode(location, exactly_one=True)
        if not res:
            return None
        return {"lat": res.latitude, "lon": res.longitude, "display_name": res.address}
    except Exception as e:
        return None

def ip_geolocate():
    # Uses ip-api.com (no API key) for approximate IP-based geolocation
    try:
        r = requests.get("http://ip-api.com/json/", timeout=8)
        r.raise_for_status()
        j = r.json()
        if j.get("status") == "success":
            return {"lat": j.get("lat"), "lon": j.get("lon"), "display_name": f"{j.get('city')}, {j.get('country')}"}
    except Exception:
        pass
    return None

def fetch_weather(lat, lon, units="metric"):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": True,
        "hourly": "temperature_2m,apparent_temperature,relativehumidity_2m,precipitation,weathercode,windspeed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,weathercode,sunrise,sunset",
        "timezone": "auto"
    }
    # Open-Meteo returns temps in Celsius always. We'll convert if user wants Fahrenheit.
    r = requests.get(OPEN_METEO_BASE, params=params, timeout=12)
    r.raise_for_status()
    return r.json()

# --- Tkinter App ---
class WeatherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Weather — Desktop GUI")
        self.geometry("950x650")
        self.resizable(True, True)

        self.units = tk.StringVar(value="metric")  # 'metric' or 'imperial'
        self.location_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Enter a location or use Auto-detect.")
        self.current_data = None
        self.weather_json = None
        self.coords = None

        self._build_ui()

    def _build_ui(self):
        # Top frame: input + controls
        top = ttk.Frame(self, padding=8)
        top.pack(side="top", fill="x")

        ttk.Label(top, text="Location:").pack(side="left")
        entry = ttk.Entry(top, textvariable=self.location_var, width=40)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda e: self._threaded(self.search_location))

        ttk.Button(top, text="Search", command=lambda: self._threaded(self.search_location)).pack(side="left", padx=4)
        ttk.Button(top, text="Auto-detect my location", command=lambda: self._threaded(self.auto_detect)).pack(side="left", padx=4)

        # Units
        units_frame = ttk.Frame(top)
        units_frame.pack(side="right")
        ttk.Label(units_frame, text="Units:").pack(side="left")
        r1 = ttk.Radiobutton(units_frame, text="Celsius", variable=self.units, value="metric", command=self._on_unit_change)
        r2 = ttk.Radiobutton(units_frame, text="Fahrenheit", variable=self.units, value="imperial", command=self._on_unit_change)
        r1.pack(side="left")
        r2.pack(side="left")

        # Status bar
        status = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status.pack(side="bottom", fill="x", padx=6, pady=4)

        # Main area: current + hourly + daily
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)

        # Left: current & hourly
        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        # Current
        self.current_frame = ttk.LabelFrame(left, text="Current", padding=8)
        self.current_frame.pack(fill="x", pady=6)

        self.lbl_location = ttk.Label(self.current_frame, text="—", font=("Segoe UI", 14, "bold"))
        self.lbl_location.pack(anchor="w")
        self.lbl_time = ttk.Label(self.current_frame, text="")
        self.lbl_time.pack(anchor="w")
        self.lbl_condition = ttk.Label(self.current_frame, text="", font=("Segoe UI", 20))
        self.lbl_condition.pack(anchor="w", pady=6)
        self.lbl_temp = ttk.Label(self.current_frame, text="", font=("Segoe UI", 22, "bold"))
        self.lbl_temp.pack(anchor="w")
        self.lbl_details = ttk.Label(self.current_frame, text="")
        self.lbl_details.pack(anchor="w")

        # Hourly forecast list
        hourly_frame = ttk.LabelFrame(left, text="Hourly (next 48h)", padding=6)
        hourly_frame.pack(fill="both", expand=True, pady=6)

        self.hourly_tree = ttk.Treeview(hourly_frame, columns=("time", "temp", "feel", "precip", "code"), show="headings", height=12)
        for col, txt in [("time","Time"),("temp","Temp"),("feel","Feels"),("precip","Precip(mm)"),("code","W")]:
            self.hourly_tree.heading(col, text=txt)
            self.hourly_tree.column(col, anchor="center", width=90)
        self.hourly_tree.pack(fill="both", expand=True)

        # Plot placeholder
        if HAVE_MPL:
            plot_frame = ttk.LabelFrame(left, text="Hourly temp chart", padding=6)
            plot_frame.pack(fill="both", expand=True, pady=6)
            self.fig = Figure(figsize=(5,2.2), dpi=100)
            self.ax = self.fig.add_subplot(111)
            self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
        else:
            ttk.Label(left, text="Install matplotlib and numpy to see charts (optional).").pack()

        # Right: daily
        right = ttk.Frame(main)
        right.pack(side="right", fill="y", padx=8)

        self.daily_frame = ttk.LabelFrame(right, text="Daily (7 days)", padding=8)
        self.daily_frame.pack(fill="y", expand=True)

        self.daily_list = ttk.Treeview(self.daily_frame, columns=("day","min","max","code"), show="headings", height=12)
        for col, txt in [("day","Day"),("min","Min"),("max","Max"),("code","W")]:
            self.daily_list.heading(col, text=txt)
            self.daily_list.column(col, anchor="center", width=120)
        self.daily_list.pack(fill="both", expand=True)

    def _set_status(self, text):
        self.status_var.set(text)

    def _threaded(self, func):
        # Run network-bound functions in a background thread to keep UI responsive
        threading.Thread(target=func, daemon=True).start()

    # --- Actions ---
    def search_location(self):
        loc = self.location_var.get().strip()
        if not loc:
            self._set_status("Type a location first.")
            return
        self._set_status(f"Geocoding '{loc}'...")
        geo = geocode_location(loc)
        if not geo:
            self._set_status("Could not find location. Try a different query.")
            return
        self.coords = (geo["lat"], geo["lon"])
        self._set_status(f"Found: {geo['display_name']}. Fetching weather...")
        try:
            self._fetch_and_display(geo["lat"], geo["lon"], geo["display_name"])
        except Exception as e:
            self._set_status(f"Error fetching weather: {e}")

    def auto_detect(self):
        self._set_status("Auto-detecting location (via IP)...")
        geo = ip_geolocate()
        if not geo:
            self._set_status("Auto-detect failed. You can type a city name instead.")
            return
        self.coords = (geo["lat"], geo["lon"])
        self.location_var.set(geo.get("display_name",""))
        self._set_status(f"Detected: {geo['display_name']}. Fetching weather...")
        try:
            self._fetch_and_display(geo["lat"], geo["lon"], geo["display_name"])
        except Exception as e:
            self._set_status(f"Error fetching weather: {e}")

    def _on_unit_change(self):
        # If data already displayed, refresh display with conversion
        if self.weather_json and self.coords:
            lat, lon = self.coords
            # re-render from cached JSON (Open-Meteo always returns Celsius, convert to F if needed)
            self._render_weather(self.weather_json)

    def _fetch_and_display(self, lat, lon, display_name):
        try:
            j = fetch_weather(lat, lon, units=self.units.get())
            self.weather_json = j
            self._render_weather(j, display_name)
            self._set_status(f"Weather updated for {display_name}.")
        except Exception as e:
            self._set_status("Failed to fetch weather: " + str(e))

    def _render_weather(self, j, display_name=None):
        # Parse & update UI. Open-Meteo provides current_weather and arrays.
        try:
            current = j.get("current_weather", {})
            timezone = j.get("timezone", "")
            hourly = j.get("hourly", {})
            daily = j.get("daily", {})

            # Show location and time
            if not display_name:
                display_name = f"{j.get('latitude'):.3f}, {j.get('longitude'):.3f}"
            self.lbl_location.config(text=display_name)
            time_now = current.get("time", datetime.utcnow().isoformat())
            # Format
            try:
                dt = datetime.fromisoformat(time_now)
                self.lbl_time.config(text=f"As of {dt.strftime('%Y-%m-%d %H:%M')}")
            except Exception:
                self.lbl_time.config(text=f"As of {time_now}")

            # Weather code -> emoji + description
            code = int(current.get("weathercode", -1)) if current else -1
            emoji, desc = map_weathercode(code)
            temp_c = float(current.get("temperature")) if current else None
            wind = current.get("windspeed", None)
            # Convert units if needed
            if self.units.get() == "imperial":
                temp_display = f"{c_to_f(temp_c):.1f} °F" if temp_c is not None else "—"
                wind_display = f"{wind * 0.621371:.1f} mph" if wind is not None else "—"
            else:
                temp_display = f"{temp_c:.1f} °C" if temp_c is not None else "—"
                wind_display = f"{wind:.1f} km/h" if wind is not None else "—"

            self.lbl_condition.config(text=f"{emoji}  {desc}")
            self.lbl_temp.config(text=temp_display)
            self.lbl_details.config(text=f"Wind: {wind_display}")

            # Hourly table: time, temp, feels, precip, code
            for i in self.hourly_tree.get_children():
                self.hourly_tree.delete(i)

            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            feels = hourly.get("apparent_temperature", [])
            precips = hourly.get("precipitation", [])
            codes = hourly.get("weathercode", [])
            # Show next 48 rows or available length
            limit = min(48, len(times))
            for idx in range(limit):
                t = times[idx]
                try:
                    dt = datetime.fromisoformat(t)
                    label = dt.strftime("%m-%d %H:%M")
                except Exception:
                    label = t
                val_temp = temps[idx]
                val_feel = feels[idx] if idx < len(feels) else ""
                val_prec = precips[idx] if idx < len(precips) else ""
                wcode = int(codes[idx]) if idx < len(codes) else -1
                em, _ = map_weathercode(wcode)
                # convert
                if self.units.get() == "imperial":
                    val_temp_display = f"{c_to_f(val_temp):.1f}"
                    val_feel_display = f"{c_to_f(val_feel):.1f}" if val_feel != "" else ""
                else:
                    val_temp_display = f"{val_temp:.1f}"
                    val_feel_display = f"{val_feel:.1f}" if val_feel != "" else ""
                self.hourly_tree.insert("", "end", values=(label, val_temp_display, val_feel_display, f"{val_prec:.1f}", em))

            # Plot hourly temperature if matplotlib is present
            if HAVE_MPL:
                try:
                    xs = [datetime.fromisoformat(t) for t in times[:limit]]
                    ys = [float(x) for x in temps[:limit]]
                    if self.units.get() == "imperial":
                        ys = [c_to_f(y) for y in ys]
                    self.ax.clear()
                    self.ax.plot(xs, ys)
                    self.ax.set_title("Hourly Temperature")
                    self.ax.set_xlabel("Time")
                    self.ax.set_ylabel("°F" if self.units.get()=="imperial" else "°C")
                    self.fig.autofmt_xdate()
                    self.canvas.draw()
                except Exception:
                    pass

            # Daily table
            for i in self.daily_list.get_children():
                self.daily_list.delete(i)
            d_times = daily.get("time", [])
            d_min = daily.get("temperature_2m_min", [])
            d_max = daily.get("temperature_2m_max", [])
            d_codes = daily.get("weathercode", [])
            for i in range(len(d_times)):
                dt_str = d_times[i]
                try:
                    dt = datetime.fromisoformat(dt_str)
                    daylabel = dt.strftime("%a %d %b")
                except:
                    daylabel = dt_str
                minv = d_min[i] if i < len(d_min) else None
                maxv = d_max[i] if i < len(d_max) else None
                if self.units.get() == "imperial":
                    min_display = f"{c_to_f(minv):.1f}" if minv is not None else "—"
                    max_display = f"{c_to_f(maxv):.1f}" if maxv is not None else "—"
                else:
                    min_display = f"{minv:.1f}" if minv is not None else "—"
                    max_display = f"{maxv:.1f}" if maxv is not None else "—"
                codeval = int(d_codes[i]) if i < len(d_codes) else -1
                em, _ = map_weathercode(codeval)
                self.daily_list.insert("", "end", values=(daylabel, min_display, max_display, em))

            # Sunrise/Sunset: display on current details if available
            try:
                sunrise = daily.get("sunrise", [None])[0]
                sunset = daily.get("sunset", [None])[0]
                if sunrise and sunset:
                    sr = datetime.fromisoformat(sunrise).strftime("%H:%M")
                    ss = datetime.fromisoformat(sunset).strftime("%H:%M")
                    # append to details
                    prev = self.lbl_details.cget("text")
                    self.lbl_details.config(text=f"{prev}    Sunrise: {sr}   Sunset: {ss}")
            except Exception:
                pass

        except Exception as ex:
            self._set_status("Error rendering weather: " + str(ex))
            return

# --- Run ---
if __name__ == "__main__":
    app = WeatherApp()
    app.mainloop()
