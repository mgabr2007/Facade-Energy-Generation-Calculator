import streamlit as st
import pandas as pd

# Function to fetch data from PVGIS TMY file
def fetch_pvgis_tmy_data(file_path):
    try:
        data = pd.read_csv(file_path, skiprows=16)  # Skip the initial 16 metadata lines
        return data
    except Exception as e:
        st.error(f"Error processing PVGIS data: {e}")
        return None

# Streamlit app interface
st.title("Fetch PVGIS TMY Data")

st.write("""
This tool fetches Typical Meteorological Year (TMY) data from a provided PVGIS CSV file.
""")

# File uploader
uploaded_file = st.file_uploader("Choose a file")

if uploaded_file is not None:
    pvgis_tmy_data = fetch_pvgis_tmy_data(uploaded_file)
    if pvgis_tmy_data is not None:
        # Display the first few rows of the data
        st.write("**PVGIS TMY Data Head**")
        st.write(pvgis_tmy_data.head(20))
