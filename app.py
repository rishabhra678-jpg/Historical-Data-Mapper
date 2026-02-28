import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

st.title("ChronoMap AI: Historical Data Mapper")
st.write("Welcome to the prototype for the AMD Slingshot Hackathon.")
st.write("Map and data extraction features are currently in development.")

# Placeholder map focused on India
m = folium.Map(location=[20.5937, 78.9629], zoom_start=5)
st_data = st_folium(m, width=700, height=500)
