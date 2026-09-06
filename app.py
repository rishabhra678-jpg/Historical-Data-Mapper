import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import AntPath
from streamlit_folium import st_folium
import plotly.express as px
import re
import os

from geocoder import HistoricalGeocoder
from nlp_engine import SpatiotemporalExtractor, PRESETS, parse_date_string

# Faction Color Configurations
FACTION_COLORS = {
    "Anglo-Saxon (Harold Godwinson)": "#ff4b4b",          # Red
    "Norman (William of Normandy)": "#3b82f6",            # Blue
    "Norwegian (Harald Hardrada)": "#10b981",             # Green
    "Grande Armée (French)": "#3b82f6",                   # Blue
    "Russian Empire": "#ff4b4b",                          # Red
    "Main Narrative": "#ff4b4b",                          # Red
    "Neutral": "#9ca3af"                                  # Gray
}

FACTION_COLORS_RGB = {
    "Anglo-Saxon (Harold Godwinson)": "255, 75, 75",
    "Norman (William of Normandy)": "59, 130, 246",
    "Norwegian (Harald Hardrada)": "16, 185, 129",
    "Grande Armée (French)": "59, 130, 246",
    "Russian Empire": "255, 75, 75",
    "Main Narrative": "255, 75, 75",
    "Neutral": "156, 163, 175"
}

# Set page config for a widescreen layout and premium title
st.set_page_config(
    page_title="Chronomap AI - Spatiotemporal Historical Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium CSS Styling (Glassmorphism, custom scrollbar, modern typography)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Main Background & Cards */
    .stApp {
        background-color: #f7f9fc;
        color: #2b2d42;
    }
    
    /* Metric Card Styling */
    .metric-card {
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
        transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
        border-color: rgba(255, 75, 75, 0.4);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08);
    }
    .metric-num {
        font-size: 2.2rem;
        font-weight: 700;
        color: #ff4b4b;
        margin-bottom: 5px;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Custom Timeline Styles */
    .timeline-container {
        border-left: 3px solid #ff4b4b;
        padding-left: 24px;
        margin-left: 20px;
        position: relative;
    }
    .timeline-event {
        margin-bottom: 30px;
        position: relative;
        background: rgba(255, 255, 255, 0.85);
        padding: 16px;
        border-radius: 8px;
        border: 1px solid rgba(0, 0, 0, 0.04);
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
    }
    .timeline-badge {
        position: absolute;
        left: -34px;
        top: 14px;
        width: 17px;
        height: 17px;
        border-radius: 50%;
        background-color: #ff4b4b;
        border: 3px solid #f7f9fc;
        box-shadow: 0 0 8px rgba(255, 75, 75, 0.3);
    }
    .timeline-date {
        font-weight: 600;
        color: #ff4b4b;
        background-color: rgba(255, 75, 75, 0.08);
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        display: inline-block;
        margin-bottom: 8px;
    }
    .timeline-loc {
        margin: 5px 0;
        font-size: 1.15rem;
        font-weight: 600;
        color: #2b2d42;
    }
    .timeline-desc {
        color: #495057;
        font-size: 0.95rem;
        line-height: 1.5;
        margin-top: 8px;
    }
    
    /* Entity Tag Highlights */
    .entity-tag-loc {
        background-color: rgba(43, 108, 176, 0.1);
        border: 1px solid rgba(43, 108, 176, 0.4);
        padding: 2px 6px;
        border-radius: 4px;
        color: #2b6cb0;
        font-weight: 600;
    }
    .entity-tag-date {
        background-color: rgba(221, 107, 32, 0.1);
        border: 1px solid rgba(221, 107, 32, 0.4);
        padding: 2px 6px;
        border-radius: 4px;
        color: #dd6b20;
        font-weight: 600;
    }
    
    /* Force st_folium map iframe dimensions to resolve blank rendering issues */
    iframe[title="streamlit_folium.st_folium"] {
        height: 400px !important;
        width: 100% !important;
        border: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Initialize Geocoder and Extractor (cached using Streamlit)
@st.cache_resource
def get_nlp_components():
    geocoder = HistoricalGeocoder()
    extractor = SpatiotemporalExtractor(geocoder)
    return geocoder, extractor

geocoder, extractor = get_nlp_components()

def render_timeline_html(events, current_step):
    events_html = ""
    for idx, ev in enumerate(events):
        loc_str = ev['location'] if ev['location'] else "Non-spatial Event"
        coords_str = f" ({ev['coords'][0]:.3f}, {ev['coords'][1]:.3f})" if ev['coords'] else ""
        is_active = (idx == current_step)
        
        faction = ev.get("faction", "Main Narrative")
        faction_color = FACTION_COLORS.get(faction, "#ff4b4b")
        faction_rgb = FACTION_COLORS_RGB.get(faction, "255, 75, 75")
        
        card_style = (
            f'background: rgba({faction_rgb}, 0.08); border: 1px solid {faction_color}; box-shadow: 0 4px 15px rgba({faction_rgb},0.08); font-weight: 500;' 
            if is_active else 
            'background: rgba(255, 255, 255, 0.9); border: 1px solid rgba(0, 0, 0, 0.05);'
        )
        badge_style = (
            'background-color: #ffdd59; box-shadow: 0 0 12px #ffdd59; border: 3px solid #f7f9fc;' 
            if is_active else 
            f'background-color: {faction_color}; box-shadow: 0 0 8px rgba({faction_rgb}, 0.3); border: 3px solid #f7f9fc;'
        )
        active_id = 'id="active-event"' if is_active else ""
        
        faction_label = f"&nbsp;|&nbsp; 🛡️ {faction}" if faction != "Main Narrative" else ""
        events_html += f"""
        <div class="timeline-event" {active_id} style="{card_style}">
            <div class="timeline-badge" style="{badge_style}"></div>
            <span class="timeline-date" style="color: {faction_color}; background-color: rgba({faction_rgb}, 0.08); {'border: 1px solid ' + faction_color + ';' if is_active else ''}">Event {idx+1} {faction_label} &nbsp;|&nbsp; {ev['date_str']}</span>
            <div class="timeline-loc">{loc_str}<span style="font-size: 0.85rem; color:#6c757d; font-weight:normal;">{coords_str}</span></div>
            <div class="timeline-desc">{ev['sentence']}</div>
        </div>
        """
        
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {{
                font-family: 'Outfit', sans-serif;
                margin: 0;
                padding: 5px;
                background-color: #f7f9fc;
                overflow-x: hidden;
            }}
            /* Custom Scrollbar */
            ::-webkit-scrollbar {{
                width: 6px;
            }}
            ::-webkit-scrollbar-track {{
                background: rgba(0,0,0,0.02);
                border-radius: 10px;
            }}
            ::-webkit-scrollbar-thumb {{
                background: rgba(0,0,0,0.15);
                border-radius: 10px;
            }}
            ::-webkit-scrollbar-thumb:hover {{
                background: rgba(0,0,0,0.3);
            }}
            .scroll-container {{
                max-height: 440px;
                overflow-y: auto;
                padding-right: 10px;
                padding-left: 5px;
                padding-top: 5px;
            }}
            .timeline-container {{
                border-left: 3px dashed #cbd5e1;
                padding-left: 24px;
                margin-left: 20px;
                position: relative;
            }}
            .timeline-event {{
                margin-bottom: 20px;
                position: relative;
                padding: 14px;
                border-radius: 10px;
                transition: all 0.3s ease;
                box-sizing: border-box;
            }}
            .timeline-badge {{
                position: absolute;
                left: -34px;
                top: 14px;
                width: 17px;
                height: 17px;
                border-radius: 50%;
                transition: all 0.3s ease;
            }}
            .timeline-date {{
                font-weight: 600;
                color: #ff4b4b;
                background-color: rgba(255, 75, 75, 0.08);
                padding: 3px 10px;
                border-radius: 20px;
                font-size: 0.8rem;
                display: inline-block;
                margin-bottom: 6px;
            }}
            .timeline-loc {{
                margin: 4px 0;
                font-size: 1.05rem;
                font-weight: 600;
                color: #2b2d42;
            }}
            .timeline-desc {{
                color: #495057;
                font-size: 0.9rem;
                line-height: 1.45;
                margin-top: 6px;
            }}
        </style>
    </head>
    <body>
        <div class="scroll-container" id="scroll-container">
            <div class="timeline-container">
                {events_html}
            </div>
        </div>
        <script>
            window.onload = function() {{
                setTimeout(function() {{
                    var activeEvent = document.getElementById("active-event");
                    var container = document.getElementById("scroll-container");
                    if (activeEvent && container) {{
                        var containerTop = container.getBoundingClientRect().top;
                        var elemTop = activeEvent.getBoundingClientRect().top;
                        var relativeTop = elemTop - containerTop + container.scrollTop;
                        
                        container.scrollTo({{
                            top: relativeTop - 20,
                            behavior: 'smooth'
                        }});
                    }}
                }}, 100);
            }}
        </script>
    </body>
    </html>
    """
    return html_content

# --- COMPACT HEADER SECTION ---
st.markdown(
    """
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 5px 0 15px 0; margin-bottom: 10px; border-bottom: 1px solid rgba(0,0,0,0.05);">
        <h2 style="font-size: 1.8rem; font-weight: 700; margin: 0; background: linear-gradient(90deg, #ff4b4b, #ff8f8f); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🌍 Chronomap AI
        </h2>
        <span style="color: #6c757d; font-size: 0.9rem; font-weight: 500;">
            Spatiotemporal NLP & GIS Historical Dashboard
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

# --- SIDEBAR: CONTROLS & ARCHIVE UPLOAD ---
with st.sidebar:
    st.markdown("### 📥 Input Archive")
    
    # Preset selection
    preset_options = list(PRESETS.keys())
        
    preset_choice = st.selectbox(
        "Select a Historical Preset:",
        options=preset_options
    )
    
    # File Uploader
    uploaded_file = st.file_uploader(
        "Or Upload custom Archive (.txt, .json):",
        type=["txt", "json"]
    )
    
    # Extract source text or JSON data based on input method
    source_text = ""
    is_json = False
    json_data = None
    
    if uploaded_file is not None:
        file_name = uploaded_file.name.lower()
        if file_name.endswith(".json"):
            import json
            try:
                json_data = json.loads(uploaded_file.read().decode("utf-8"))
                is_json = True
                st.success("Custom JSON file uploaded successfully!")
            except Exception as e:
                st.error(f"Error parsing uploaded JSON: {e}")
        else:
            source_text = uploaded_file.read().decode("utf-8")
            st.success("Custom text file uploaded successfully!")
    else:
        source_text = PRESETS[preset_choice]

    # NLP Settings Expander
    st.markdown("---")
    st.markdown("### ⚙️ Engine Parameters")
    with st.expander("Adjust Extraction Settings", expanded=False):
        use_spacy = st.toggle("Use spaCy Named Entity Recognition", value=True, help="If disabled, uses robust regex patterns to find location entities.")
        if not use_spacy:
            st.info("Using rules-based entity extraction.")
            
        map_style = st.selectbox(
            "Map Theme:",
            options=[
                "CartoDB Positron (Light Minimal)",
                "CartoDB Dark Matter (Dark)",
                "National Geographic (Historical)",
                "OpenStreetMap (Standard)",
                "Esri Topographic",
                "Esri Satellite Imagery",
                "Esri World Street"
            ],
            index=0
        )
        
        carto_api_key = ""
        if "CartoDB" in map_style:
            carto_api_key = st.text_input(
                "CARTO API Key (Optional):",
                value="",
                type="password",
                help="Optional: Enter your free CARTO API key (from carto.com/basemaps/apikey) to remove watermarks."
            )
        
    st.markdown("---")
    st.markdown(
        """
        <div style="font-size: 0.85rem; color: #6a6f7a; line-height: 1.4;">
            <b>Chronomap AI v1.0</b><br/>
            Uses Named Entity Recognition (NER) to locate places, parses complex date strings chronologically, and maps spatial movement ("narrative motion").
        </div>
        """,
        unsafe_allow_html=True
    )

# --- NLP / JSON PROCESSING ---
with st.spinner("Processing narrative & geocoding locations..."):
    if is_json and json_data:
        # Parse from JSON structure (hastings_data.json format)
        events = []
        raw_timeline = json_data.get("timeline", [])
        for idx, item in enumerate(raw_timeline):
            date_str = item.get("date", "Unknown Date")
            lat = item.get("coordinates", {}).get("lat", None)
            lng = item.get("coordinates", {}).get("lng", None)
            
            description = item.get("description", "")
            event_name = item.get("event", "Event")
            faction = item.get("faction", None)
            if not faction:
                faction = extractor.classify_faction(description, event_name, json_data.get("narrative", ""))
                
            events.append({
                "id": idx + 1,
                "sentence_idx": idx,
                "date_str": date_str,
                "sort_key": parse_date_string(date_str),
                "location": event_name,
                "coords": (lat, lng) if (lat is not None and lng is not None) else None,
                "sentence": description,
                "summary": event_name,
                "faction": faction
            })
        
        # Sort events chronologically
        events.sort(key=lambda x: (x["sort_key"] if x["sort_key"] else (9999, 12, 31), x["sentence_idx"]))
        for idx, ev in enumerate(events):
            ev["id"] = idx + 1
            
        motion_vectors = extractor.calculate_motion_statistics(events)
        
        # Build text description representation for the document viewer tab
        source_text = f"Project: {json_data.get('project', 'Chronomap AI')}\n"
        source_text += f"Narrative: {json_data.get('narrative', 'Norman Conquest')}\n\n"
        for ev in events:
            source_text += f"[{ev['date_str']}] {ev['location']}: {ev['sentence']}\n"
    else:
        # Toggle spacy status on the extractor
        extractor.use_spacy = use_spacy

        # Extract spatiotemporal events
        events = extractor.process_narrative(source_text)
        motion_vectors = extractor.calculate_motion_statistics(events)

# Ensure events exist
if not events:
    st.warning("⚠️ No spatiotemporal events could be extracted. Try adjusting the text or check formatting.")
    st.stop()

# --- METRIC CALCULATIONS & SIDEBAR DISPLAY ---
# Filter valid geocoded locations
geocoded_events = [ev for ev in events if ev["coords"] is not None]
total_locations = len(set([ev["location"] for ev in geocoded_events if ev["location"]]))
total_distance = sum([v["distance_km"] for v in motion_vectors])

# Estimate duration (years) if possible
years = [ev["sort_key"][0] for ev in events if ev["sort_key"] and ev["sort_key"][0] != 9999]
if years:
    duration_str = f"{min(years)} - {max(years)}" if max(years) != min(years) else f"Year {min(years)}"
else:
    duration_str = "N/A"

# Append summary metrics to sidebar
with st.sidebar:
    st.markdown("---")
    st.markdown("### 📊 Narrative Summary")
    st.markdown(
        f"""
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;">
            <div style="background: rgba(255, 255, 255, 0.95); border: 1px solid rgba(0, 0, 0, 0.05); border-radius: 8px; padding: 10px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.02);">
                <div style="font-size: 1.4rem; font-weight: 700; color: #ff4b4b; line-height: 1.2;">{len(events)}</div>
                <div style="font-size: 0.65rem; color: #6c757d; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Events</div>
            </div>
            <div style="background: rgba(255, 255, 255, 0.95); border: 1px solid rgba(0, 0, 0, 0.05); border-radius: 8px; padding: 10px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.02);">
                <div style="font-size: 1.4rem; font-weight: 700; color: #ff4b4b; line-height: 1.2;">{total_locations}</div>
                <div style="font-size: 0.65rem; color: #6c757d; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Locations</div>
            </div>
            <div style="background: rgba(255, 255, 255, 0.95); border: 1px solid rgba(0, 0, 0, 0.05); border-radius: 8px; padding: 10px; text-align: center; grid-column: span 2; box-shadow: 0 2px 8px rgba(0,0,0,0.02);">
                <div style="font-size: 1.25rem; font-weight: 700; color: #ff4b4b; line-height: 1.2;">{total_distance:,.1f} km</div>
                <div style="font-size: 0.65rem; color: #6c757d; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Est. Narrative Motion</div>
            </div>
            <div style="background: rgba(255, 255, 255, 0.95); border: 1px solid rgba(0, 0, 0, 0.05); border-radius: 8px; padding: 10px; text-align: center; grid-column: span 2; box-shadow: 0 2px 8px rgba(0,0,0,0.02);">
                <div style="font-size: 1.1rem; font-weight: 700; color: #ff4b4b; line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{duration_str}</div>
                <div style="font-size: 0.65rem; color: #6c757d; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Historical Period</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- INITIALIZE PLAYBACK STATE ---
if "current_step" not in st.session_state:
    st.session_state.current_step = 0

text_key = f"text_hash_{len(source_text)}"
if "last_text_key" not in st.session_state or st.session_state.last_text_key != text_key:
    st.session_state.last_text_key = text_key
    st.session_state.current_step = 0
    # Clear select slider state to avoid options mismatch when switching presets
    if "chrono_select_slider" in st.session_state:
        del st.session_state.chrono_select_slider

# --- MAIN LAYOUT: MAP & TIMELINE SIDE-BY-SIDE ---
num_steps = len(events)

# Clamp current step just in case
if st.session_state.current_step >= num_steps:
    st.session_state.current_step = num_steps - 1

# Columns: Left for Map & Controls, Right for Complete Scrollable Timeline
col_map, col_timeline = st.columns([5, 3])

with col_map:
    # Active event from complete list
    active_event = events[st.session_state.current_step]
    
    # Map focus on active coordinates
    active_coords = active_event["coords"]
    
    # Set dynamic zoom start and fallback center based on historical preset scale
    zoom_val = 5
    fallback_center = (55.0, 3.0)  # default focus on North Europe (North Sea)
    
    if "Marco Polo" in preset_choice or (json_data and "Marco Polo" in json_data.get("narrative", "")):
        zoom_val = 4
        fallback_center = (39.0, 75.0)  # Silk Road / Kashgar region center
    elif "Napoleon" in preset_choice or (json_data and "Napoleon" in json_data.get("narrative", "")):
        zoom_val = 5
        fallback_center = (55.0, 30.0)  # Western Russia Campaign center
    elif "Norman" in preset_choice or (json_data and "Norman" in json_data.get("narrative", "")):
        zoom_val = 5
        fallback_center = (55.0, 3.0)   # North Europe center
        
    # Fallback if active event has no coords: find nearest preceding geocoded event
    if active_coords is None:
        for temp_ev in reversed(events[:st.session_state.current_step]):
            if temp_ev["coords"] is not None:
                active_coords = temp_ev["coords"]
                break
    if active_coords is None:
        active_coords = fallback_center
    
    # Map Tile Configuration
    carto_positron_url = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
    carto_dark_url = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    if carto_api_key:
        carto_positron_url += f"?key={carto_api_key}"
        carto_dark_url += f"?key={carto_api_key}"
        
    tile_providers = {
        "CartoDB Positron (Light Minimal)": {
            "tiles": carto_positron_url if carto_api_key else "CartoDB Positron",
            "attr": "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors &copy; <a href='https://carto.com/attributions'>CARTO</a>" if carto_api_key else None
        },
        "CartoDB Dark Matter (Dark)": {
            "tiles": carto_dark_url if carto_api_key else "CartoDB dark_matter",
            "attr": "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors &copy; <a href='https://carto.com/attributions'>CARTO</a>" if carto_api_key else None
        },
        "National Geographic (Historical)": {
            "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}",
            "attr": "Tiles &copy; Esri &mdash; National Geographic, DeLorme, NAVTEQ"
        },
        "OpenStreetMap (Standard)": {
            "tiles": "OpenStreetMap",
            "attr": None
        },
        "Esri Topographic": {
            "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
            "attr": "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, USGS"
        },
        "Esri Satellite Imagery": {
            "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "attr": "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics"
        },
        "Esri World Street": {
            "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
            "attr": "Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ"
        }
    }
    
    selected_tile = tile_providers.get(map_style, tile_providers["CartoDB Positron (Light Minimal)"])
    
    # Initialize Folium Map
    if selected_tile["attr"]:
        m = folium.Map(
            location=active_coords,
            zoom_start=zoom_val,
            tiles=selected_tile["tiles"],
            attr=selected_tile["attr"]
        )
    else:
        m = folium.Map(
            location=active_coords,
            zoom_start=zoom_val,
            tiles=selected_tile["tiles"]
        )
    
    # Group events by faction to draw separate tracks
    factions_data = {}
    for ev in geocoded_events:
        faction = ev.get("faction", "Main Narrative")
        if faction not in factions_data:
            factions_data[faction] = []
        factions_data[faction].append(ev)
        
    # Draw paths for each faction
    for faction, faction_events in factions_data.items():
        color = FACTION_COLORS.get(faction, "#ff4b4b")
        
        # Draw full track in dashed color
        path_coords_full = [ev["coords"] for ev in faction_events]
        if len(path_coords_full) > 1:
            folium.PolyLine(
                locations=path_coords_full,
                color=color,
                weight=2,
                opacity=0.3,
                dash_array="5, 10",
                tooltip=f"{faction} Route"
            ).add_to(m)
            
        # Draw active path for this faction up to current active event
        active_faction_events = [ev for ev in faction_events if ev["id"] <= active_event["id"]]
        path_coords_active = [ev["coords"] for ev in active_faction_events]
        if len(path_coords_active) > 1:
            AntPath(
                locations=path_coords_active,
                dash_array=[10, 20],
                delay=1000,
                color=color,
                pulse_color="#ffffff",
                weight=4,
                opacity=0.9,
                tooltip=f"Active {faction} Route"
            ).add_to(m)
            
    # Place markers
    for idx, ev in enumerate(geocoded_events):
        is_active = (ev["id"] == active_event["id"])
        faction = ev.get("faction", "Main Narrative")
        faction_color = FACTION_COLORS.get(faction, "#ff4b4b")
        
        marker_color = "#ffdd59" if is_active else faction_color
        border_color = faction_color if is_active else "#ffffff"
        glow = f"0 0 15px {faction_color}" if is_active else "0 0 6px rgba(0,0,0,0.3)"
        z_index = 1000 if is_active else 100
        scale = "scale(1.25)" if is_active else "scale(1.0)"
        
        icon_html = f"""
        <div style="
            background-color: {marker_color};
            border: 2px solid {border_color};
            border-radius: 50%;
            color: {'#111111' if is_active else 'white'};
            font-weight: bold;
            text-align: center;
            width: 22px;
            height: 22px;
            line-height: 18px;
            font-size: 11px;
            box-shadow: {glow};
            z-index: {z_index};
            transform: {scale};
            transition: all 0.3s ease;
        ">{idx+1}</div>
        """
        
        popup_html = f"""
        <div style="font-family: 'Outfit', sans-serif; font-size: 12px; line-height: 1.4; color: #333333; max-width: 250px;">
            <h4 style="margin: 0 0 5px 0; color: {faction_color};">Step {idx+1}: {ev['location']}</h4>
            <b>Faction:</b> {faction}<br/>
            <b>Date:</b> {ev['date_str']}<br/>
            <b>Event:</b> {ev['sentence']}<br/>
        </div>
        """
        
        folium.Marker(
            location=ev["coords"],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.DivIcon(
                html=icon_html,
                icon_size=(22, 22),
                icon_anchor=(11, 11)
            ),
            tooltip=f"Step {idx+1}: {ev['location']} ({ev['date_str']}) - {faction}"
        ).add_to(m)
        
    # Render rectangular map using st_folium with a static key for high-performance rendering without iframe flashes
    st_folium(
        m,
        height=400,
        use_container_width=True,
        key="chronomap_folium_map",
        returned_objects=[]
    )
    
    # Chronological controls below the map
    st.markdown("<h4 style='margin: 10px 0 5px 0; font-size: 1.05rem; font-weight: 600;'>🎬 Chronological Narrative Navigator</h4>", unsafe_allow_html=True)
    
    # Options for chronological slider
    chrono_options = [
        f"{idx+1}. {ev['date_str']} | {ev['location'] if ev['location'] else 'Event'}"
        for idx, ev in enumerate(events)
    ]
    
    # Initialize slider key if not present in session state
    if "chrono_select_slider" not in st.session_state:
        st.session_state.chrono_select_slider = chrono_options[st.session_state.current_step]
    
    # Render select-slider
    selected_option = st.select_slider(
        "Navigator Slider",
        options=chrono_options,
        key="chrono_select_slider",
        label_visibility="collapsed"
    )
    st.session_state.current_step = chrono_options.index(selected_option)
    
    # Define callbacks to mutate state BEFORE widgets are instantiated
    def prev_step_cb():
        if st.session_state.current_step > 0:
            st.session_state.current_step -= 1
            st.session_state.chrono_select_slider = chrono_options[st.session_state.current_step]

    def next_step_cb():
        if st.session_state.current_step < num_steps - 1:
            st.session_state.current_step += 1
            st.session_state.chrono_select_slider = chrono_options[st.session_state.current_step]

    def reset_step_cb():
        st.session_state.current_step = 0
        st.session_state.chrono_select_slider = chrono_options[0]

    # Controls columns
    col_ctrl_btn, col_dist = st.columns([1.5, 2])
    with col_ctrl_btn:
        col_btn_prev, col_btn_next, col_btn_reset = st.columns(3)
        with col_btn_prev:
            st.button("⏮️ Prev", disabled=(st.session_state.current_step == 0), on_click=prev_step_cb, width="stretch")
        with col_btn_next:
            st.button("Next ⏭️", disabled=(st.session_state.current_step == num_steps - 1), on_click=next_step_cb, width="stretch")
        with col_btn_reset:
            st.button("🔄 Reset", on_click=reset_step_cb, width="stretch")
            
    # Display distance traveler
    with col_dist:
        if st.session_state.current_step > 0 and active_event["coords"] is not None:
            active_faction = active_event.get("faction", "Main Narrative")
            faction_color = FACTION_COLORS.get(active_faction, "#ff4b4b")
            faction_rgb = FACTION_COLORS_RGB.get(active_faction, "255, 75, 75")
            
            prev_geo = None
            for temp_ev in reversed(events[:st.session_state.current_step]):
                if temp_ev["coords"] is not None and temp_ev.get("faction") == active_faction:
                    prev_geo = temp_ev
                    break
                    
            if prev_geo:
                from geopy.distance import geodesic
                distance = geodesic(prev_geo["coords"], active_event["coords"]).kilometers
                st.markdown(
                    f"""
                    <div style="background: rgba({faction_rgb}, 0.05); padding: 5px 10px; border-radius: 6px; border: 1px solid {faction_color}; font-size: 0.85rem; color: {faction_color}; font-weight: 500; height: 38px; line-height: 28px; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        🚚 <b>+{distance:,.1f} km</b> from <i>{prev_geo['location']}</i> ({active_faction.split(' ')[0]})
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"""
                    <div style="background: rgba({faction_rgb}, 0.05); padding: 5px 10px; border-radius: 6px; border: 1px solid {faction_color}; font-size: 0.85rem; color: {faction_color}; font-weight: 500; height: 38px; line-height: 28px; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        🚩 <b>Start of track</b> ({active_faction.split(' ')[0]})
                    </div>
                    """,
                    unsafe_allow_html=True
                )

with col_timeline:
    st.markdown("<h3 style='margin: 0 0 10px 0; font-size: 1.3rem;'>📅 Chronological Timeline</h3>", unsafe_allow_html=True)
    # Render the timeline inside a custom iframe component with CSS & JS auto-scrolling
    html_code = render_timeline_html(events, st.session_state.current_step)
    st.iframe(html_code, height=480)

# --- LOWER SECTION: DATA, ANALYTICS & SOURCES ---
st.markdown("<br/><br/>", unsafe_allow_html=True)
st.markdown("---")

tab_milestones, tab_analytics, tab_viewer = st.tabs([
    "📊 Milestone Timeline Chart",
    "📊 NLP Metrics & Table",
    "📖 Source Document Viewer"
])

# 1. Milestone Timeline
with tab_milestones:
    st.subheader("Event Sequence Milestones")
    st.markdown("Hover over the milestone diamonds below to inspect chronological details.")
    
    milestones = []
    for idx, ev in enumerate(events):
        loc_display = ev["location"] if ev["location"] else "Non-spatial"
        milestones.append({
            "Step": idx + 1,
            "Date": ev["date_str"],
            "Location": loc_display,
            "Event": ev["sentence"][:60] + "..." if len(ev["sentence"]) > 60 else ev["sentence"],
            "Description": ev["sentence"],
            "Y": 0
        })
    df_milestones = pd.DataFrame(milestones)
    
    fig_timeline = px.scatter(
        df_milestones,
        x="Step",
        y="Y",
        text="Date",
        hover_data={"Step": True, "Date": True, "Location": True, "Event": True, "Y": False},
        template="plotly_white",
        height=180
    )
    fig_timeline.update_traces(
        marker=dict(size=18, color="#ff4b4b", symbol="diamond", line=dict(width=2, color="white")),
        textposition="top center",
        textfont=dict(color="#b22222", size=10)
    )
    fig_timeline.update_xaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.05)",
        tickmode="linear",
        tick0=1,
        dtick=1,
        title="Event Sequence Step #"
    )
    fig_timeline.update_yaxes(showgrid=False, showticklabels=False, title="")
    fig_timeline.update_layout(
        margin=dict(l=30, r=30, t=10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis_range=[-0.5, 0.5]
    )
    st.plotly_chart(fig_timeline, width="stretch")

# 2. NLP Metrics & Table
with tab_analytics:
    st.subheader("NLP Extraction Metrics & Dataset")
    
    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.markdown("#### Spatiotemporal Motion Log")
        if motion_vectors:
            df_motion = pd.DataFrame(motion_vectors)
            df_motion_clean = pd.DataFrame({
                "Seq": range(1, len(df_motion) + 1),
                "Origin": df_motion["from_loc"],
                "Destination": df_motion["to_loc"],
                "Start Date": df_motion["from_date"],
                "Arrival Date": df_motion["to_date"],
                "Distance (km)": df_motion["distance_km"]
            })
            st.dataframe(df_motion_clean, width="stretch", hide_index=True)
        else:
            st.info("No movement steps recorded (requires at least 2 geocoded points).")

    with col_r:
        st.markdown("#### Location Frequencies")
        loc_names = [ev["location"] for ev in events if ev["location"]]
        if loc_names:
            loc_counts = pd.Series(loc_names).value_counts().reset_index()
            loc_counts.columns = ["Location", "Occurrences"]
            
            fig = px.bar(
                loc_counts,
                x="Occurrences",
                y="Location",
                orientation='h',
                color="Occurrences",
                color_continuous_scale="Reds",
                template="plotly_white",
                height=300
            )
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                coloraxis_showscale=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No location statistics to map.")

    st.markdown("---")
    st.markdown("#### Complete Extracted Dataset")
    raw_extracted_df = pd.DataFrame([
        {
            "ID": ev["id"],
            "Parsed Date": ev["date_str"],
            "Location Entity": ev["location"] if ev["location"] else "None",
            "Latitude": ev["coords"][0] if ev["coords"] else np.nan,
            "Longitude": ev["coords"][1] if ev["coords"] else np.nan,
            "Sentence Snippet": ev["sentence"]
        }
        for ev in events
    ])
    st.dataframe(raw_extracted_df, width="stretch", hide_index=True)
    
    csv = raw_extracted_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Download Spatiotemporal Dataset as CSV",
        csv,
        "spatiotemporal_historical_data.csv",
        "text/csv",
        key='download-csv'
    )

# 3. Source Document Viewer
with tab_viewer:
    st.subheader("Source Historical Archive")
    st.markdown(
        "Here is the raw input text. Extracted named entities are highlighted: "
        "<span class='entity-tag-loc'>Locations / Places</span> and <span class='entity-tag-date'>Dates</span>.",
        unsafe_allow_html=True
    )
    
    highlighted_html = source_text
    all_locations = sorted(list(set([ev["location"] for ev in events if ev["location"]])), key=len, reverse=True)
    all_dates = sorted(list(set([ev["date_str"] for ev in events if ev["date_str"]])), key=len, reverse=True)
    
    for dt in all_dates:
        escaped_dt = re.escape(dt)
        highlighted_html = re.sub(
            rf"\b({escaped_dt})\b", 
            rf"<span class='entity-tag-date'>\1</span>", 
            highlighted_html, 
            flags=re.IGNORECASE
        )
        
    for loc in all_locations:
        escaped_loc = re.escape(loc)
        pattern = rf"\b({escaped_loc})\b" if re.match(r"^\w+$", loc) else rf"({escaped_loc})"
        highlighted_html = re.sub(
            pattern, 
            rf"<span class='entity-tag-loc'>\1</span>", 
            highlighted_html, 
            flags=re.IGNORECASE
        )

    st.markdown(
        f"""
        <div style="
            background-color: rgba(255, 255, 255, 0.85);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 12px;
            padding: 24px;
            font-size: 1.1rem;
            line-height: 1.8;
            color: #2b2d42;
            white-space: pre-wrap;
        ">{highlighted_html}</div>
        """,
        unsafe_allow_html=True
    )
