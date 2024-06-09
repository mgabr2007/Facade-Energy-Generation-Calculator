import pandas as pd
import streamlit as st

# Function to fetch data from PVGIS
def fetch_pvgis_data(file_path):
    try:
        data = pd.read_csv(file_path, skiprows=1, header=None)
        data.columns = ['Index', 'Timestamp', 'Col1', 'Col2', 'Col3', 'Col4', 'Col5']
        data['Timestamp'] = pd.to_datetime(data['Timestamp'], format='%Y%m%d:%H%M', errors='coerce')
        data = data.dropna(subset=['Timestamp'])  # Drop rows where 'Timestamp' could not be parsed
        data = data.set_index('Timestamp')
        return data
    except Exception as e:
        st.error(f"Error processing PVGIS data: {e}")
        return None

# Streamlit app interface
st.title("Fetch PVGIS Data")

st.write("""
This tool fetches solar irradiance data from a provided PVGIS CSV file.
""")

# Load the provided PVGIS data
file_path_new = '/mnt/data/2024-06-09T21-26_export.csv'
pvgis_data_new = fetch_pvgis_data(file_path_new)

if pvgis_data_new is not None:
    # Display the first few rows of the data
    st.write("**PVGIS Data Head**")
    st.write(pvgis_data_new.head(20))
