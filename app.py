import streamlit as st
import pandas as pd
import requests
from io import StringIO

# Function to fetch data from PVGIS
def fetch_pvgis_data(latitude, longitude, start_year, end_year):
    url = (
        f"https://re.jrc.ec.europa.eu/api/v5_2/seriescalc?"
        f"lat={latitude}&lon={longitude}&startyear={start_year}&endyear={end_year}&outputformat=csv"
    )
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = pd.read_csv(StringIO(response.text), skiprows=10)
            return data
        else:
            st.error(f"Error fetching PVGIS data: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Error fetching PVGIS data: {e}")
        return None

# Streamlit app interface
st.title("Fetch PVGIS Data")

st.write("""
This tool fetches solar irradiance data from PVGIS based on user inputs for location and time period.
""")

# User inputs
latitude = st.number_input("Location Latitude", min_value=-90.0, max_value=90.0, value=40.7128, help="The geographic latitude of the location.")
longitude = st.number_input("Location Longitude", min_value=-180.0, max_value=180.0, value=-74.0060, help="The geographic longitude of the location.")
start_year = st.number_input("Start Year", min_value=2005, max_value=2020, value=2020, help="The start year for the data fetch.")
end_year = st.number_input("End Year", min_value=2005, max_value=2020, value=2020, help="The end year for the data fetch.")

if st.button("Fetch Data"):
    # Fetch PVGIS data
    pvgis_data = fetch_pvgis_data(latitude, longitude, start_year, end_year)

    if pvgis_data is not None:
        # Display the first few rows of the data
        st.write("**PVGIS Data Head**")
        st.write(pvgis_data.head())
