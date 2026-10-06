# TripSphere — README

A Google Maps-inspired personal travel application built with Python, PySide6, and OpenStreetMap.

## Features

- 🌍 **Cinematic Earth Startup** — animated rotating globe with star parallax and zoom transition
- 🗺 **Interactive Leaflet Map** — dark-themed, panning/zooming, custom markers
- 🔎 **Place Search** — powered by Nominatim geocoding (no API key required)
- 📏 **Routing & Distance** — OSRM routing with haversine fallback
- 📍 **Nearby Places** — Overpass API POI search by category
- ✈ **Trip Planner** — multi-stop trips with budget tracking
- 💰 **Expense Tracker** — categorized expenses, per-trip and global
- 📊 **Budget Analytics** — donut, bar, line, and gauge charts
- 📔 **Travel Journal** — rich entries with mood tracking and photo attachment
- ⭐ **Favorites** — save any place on the map
- 🎲 **Surprise Me** — random destination discovery
- ⚙ **Settings** — profile, currency, travel mode preferences

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Configure environment
cp .env.example .env
# Edit .env to add your NOMINATIM_USER_AGENT

# 3. Run
python main.py
```

## Tech Stack

| Component | Library |
|-----------|---------|
| UI Framework | PySide6 (Qt6) |
| Map Engine | Leaflet.js via QWebEngineView |
| Database | SQLite (thread-safe singleton) |
| Charts | Matplotlib (QtAgg backend) |
| Geocoding | OpenStreetMap Nominatim |
| Routing | OSRM (free, no key required) |
| POI Search | OpenStreetMap Overpass API |
| Globe Texture | Pillow (PIL) procedural rendering |
| HTTP | Requests |

## Project Structure

```
travel_app/
├── main.py                  # Entry point
├── requirements.txt
├── .env.example
├── data/
│   └── destinations.json    # 20 curated destinations
├── app/
│   ├── config.py            # Colors, fonts, constants, QSS
│   ├── api/
│   │   ├── geocoding.py     # Nominatim search/geocode
│   │   ├── routing.py       # OSRM multi-stop routing
│   │   └── places.py        # Overpass nearby POIs
│   ├── database/
│   │   ├── db.py            # Thread-safe SQLite manager
│   │   ├── models.py        # Schema creation
│   │   ├── repositories.py  # Data access layer
│   │   └── seed_data.py     # Initial data seeding
│   ├── map/
│   │   ├── map.html         # Leaflet map + JS bridge
│   │   └── map_view.py      # Qt wrapper with Python API
│   ├── services/
│   │   ├── trip_service.py
│   │   ├── expense_service.py
│   │   ├── journal_service.py
│   │   └── recommendation_service.py
│   └── ui/
│       ├── startup.py       # Cinematic Earth screen
│       ├── main_window.py   # Root window + page router
│       ├── dashboard.py     # Home screen
│       ├── explore.py       # Map + search + routing
│       ├── trips.py         # Trip list + create
│       ├── trip_detail.py   # Trip map + expenses + stops
│       ├── expenses.py      # Global expense tracker
│       ├── budget.py        # Analytics charts
│       ├── journal.py       # Travel journal
│       ├── favorites.py     # Saved places
│       ├── random_dest.py   # Surprise Me
│       ├── settings.py      # User preferences
│       └── widgets/
│           ├── sidebar.py   # Animated collapsible nav
│           ├── cards.py     # GlassCard, TripCard, PlaceCard…
│           ├── charts.py    # Matplotlib chart widgets
│           ├── loading.py   # Spinner, empty state, error
│           └── search_bar.py # Search with suggestions
```

## No API Keys Required

All default functionality uses free, no-key APIs:
- **Nominatim** (OpenStreetMap geocoding) — 1 req/sec limit respected automatically
- **OSRM** (routing) — public demo server
- **Overpass** (POI search) — public API
- **CartoDB Dark Matter** (map tiles) — free tiles

## Notes

- All data is stored locally in `data/tripsphere.db`
- First launch seeds 20 curated destinations and a demo trip
- The app works offline with cached search results and SQLite fallback data
