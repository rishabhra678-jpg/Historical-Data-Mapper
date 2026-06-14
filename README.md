# Chronomap AI: Spatiotemporal Historical Dashboard

An interactive Streamlit web dashboard designed to extract, analyze, and visualize the spatiotemporal progression of historical events from raw textual archives. Using Named Entity Recognition (NER), date parsing algorithms, and Geographic Information Systems (GIS), Chronomap AI converts plain text narratives into interactive maps, chronological timelines, and movement analytics.

---

### Original User Prompt

```text
create a interactive streamlit webdashbord which plots the spatiotemporal data of historical events using NLP and GIS . It works on that way user upload the historical archives then the interactive map generates and plot those spatiotemporal data like date , coordinates  and motion of the historical narrative and explain the user end to end history  of that particular event [NOTE : Also create a read me file of this project and write this promt their. ]
```

---

## Key Features

1. **Dual NLP Entity Extraction Engine**: Uses `spaCy`'s pre-trained Named Entity Recognition (NER) for high-accuracy extraction of geopolitical entities (`GPE`) and locations (`LOC`), coupled with a robust regex-based backup parser for zero-dependency local runs.
2. **GIS Mapping & Motion Tracking**: Maps the sequential path of the historical narrative onto an interactive Leaflet map (rendered via `folium` and `streamlit-folium`). Visualizes motion routes using animated `AntPath` flows to convey the direction and speed of the narrative over time.
3. **SQLite Geocoding Cache & Fallbacks**: Utilizes `geopy` and the free OpenStreetMap Nominatim API with a local SQLite caching database (`geocoding_cache.db`) to avoid API rate limiting. Includes an offline dictionary of common historical landmarks for fallback operation.
4. **Interactive Timeline & Annotations**: Visualizes the chronologically ordered events on a custom HTML/CSS vertical timeline.
5. **Entity Visualizer & Analysis**: Displays the original document with highlighted location and date annotations, alongside movement analytics (estimated cumulative travel distances and location occurrences).

---

## Preset Archives Included

To demonstrate immediate capability, the dashboard comes preloaded with three narratives:
- **The Norman Conquest of 1066** (Detailing King Harold's northern defense against Norway, William's landing at Pevensey, the Battle of Hastings, and Westminster Abbey coronation).
- **Napoleon's Russian Campaign of 1812** (Detailing the advance to Moscow, Battle of Borodino, Moscow fire, and the disastrous winter retreat across the Berezina).
- **Marco Polo's Journey to China (1271-1295)** (Detailing the Silk Road route from Venice, Acre, Jerusalem, Hormuz, Dunhuang, Shangdu, and Cambaluc).

---

## Installation & Setup

Ensure you have Python 3.8+ installed, then follow these steps:

### 1. Install Dependencies
Install all package requirements listed in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 2. Download the NLP Language Model
By default, the dashboard attempts to download the spaCy English language model automatically. If you want to download it manually:
```bash
python -m spacy download en_core_web_sm
```

### 3. Run the Streamlit Dashboard
Launch the local web server:
```bash
streamlit run app.py
```
Open the provided local URL (typically `http://localhost:8501`) in your browser to interact with the dashboard.
