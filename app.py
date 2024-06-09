import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from io import StringIO

# Function to fetch data from PVGIS
def fetch_pvgis_data(latitude, longitude, start_date, end_date):
    start_year = max(start_date.year, 2005)
    end_year = min(end_date.year, 2020)
    
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

# Function to interpolate NaN values
def interpolate_nan_values(series):
    return series.interpolate(method='linear').fillna(0)

# Streamlit app interface
st.title("Facade Energy Generation Calculator")

st.write("""
This tool calculates the potential energy generation from a building facade based on user inputs such as facade azimuth, location, study time, and facade area. 
For more accurate results, detailed meteorological data specific to your location is recommended.
""")

# User inputs
facade_azimuth = st.number_input("Facade Azimuth (degrees)", min_value=0, max_value=360, value=180, help="The compass direction the facade is facing, in degrees. 0° is North, 90° is East, 180° is South, and 270° is West.")
latitude = st.number_input("Location Latitude", min_value=-90.0, max_value=90.0, value=40.7128, help="The geographic latitude of the location.")
longitude = st.number_input("Location Longitude", min_value=-180.0, max_value=180.0, value=-74.0060, help="The geographic longitude of the location.")
study_start_date = st.date_input("Study Start Date", value=datetime(2024, 6, 1), help="The start date for the energy generation study.")
study_end_date = st.date_input("Study End Date", value=datetime(2024, 6, 30), help="The end date for the energy generation study.")
facade_area = st.number_input("Facade Area (m²)", min_value=1.0, value=100.0, help="The area of the facade in square meters.")
system_losses = st.number_input("System Losses (%)", min_value=0.0, max_value=100.0, value=15.0, help="Percentage of system losses including inverter efficiency, wiring losses, and other factors.")

if st.button("Calculate Energy Generation"):
    # Validate input dates
    if study_start_date >= study_end_date:
        st.error("End date must be after start date.")
    else:
        # Generate time range
        times = pd.date_range(start=study_start_date, end=study_end_date, freq='H', tz='Etc/GMT+0')

        # Fetch PVGIS data
        pvgis_data = fetch_pvgis_data(latitude, longitude, study_start_date, study_end_date)

        if pvgis_data is None:
            st.error("Unable to fetch sufficient data from available sources.")
            st.stop()

        # Display actual column names to identify correct ones
        st.write("**PVGIS Data Columns**")
        st.write(pvgis_data.columns)

        # Identify the column for Plane of Array (POA) irradiance
        possible_poa_cols = ['G(i) poa', 'G(i)', 'G(h)']  # Example possible columns for POA
        poa_col = next((col for col in possible_poa_cols if col in pvgis_data.columns), None)

        if not poa_col:
            st.error("Required irradiance data columns are missing from the PVGIS data.")
            st.stop()

        # Interpolate NaN values
        pvgis_data[poa_col] = interpolate_nan_values(pd.to_numeric(pvgis_data[poa_col], errors='coerce'))

        # Ensure the timestamp column is converted to datetime and set as the index
        try:
            timestamp_column = pvgis_data.columns[0]
            pvgis_data['time'] = pd.to_datetime(pvgis_data[timestamp_column], format='%Y%m%d:%H%M', errors='coerce')
            pvgis_data = pvgis_data.dropna(subset=['time'])  # Drop rows where 'time' could not be parsed
            pvgis_data = pvgis_data.set_index('time')
            pvgis_data = pvgis_data[~pvgis_data.index.duplicated(keep='first')]  # Remove duplicate timestamps
            pvgis_data = pvgis_data.tz_localize('Etc/GMT+0')
        except Exception as e:
            st.error(f"Error processing time data: {e}")
            st.stop()

        # Sort the index to ensure it is monotonic
        pvgis_data = pvgis_data.sort_index()

        # Align data to the study period
        try:
            pvgis_data = pvgis_data.reindex(times, method='nearest')
        except Exception as e:
            st.error(f"Error reindexing data: {e}")
            st.stop()
        
        # Get irradiance data
        poa_irradiance = pvgis_data[poa_col]
        
        # Debug: Ensure inputs are Series with matching indices
        st.write("**POA Irradiance Head**")
        st.write(poa_irradiance.head())

        # Sum the plane of array irradiance
        total_poa_irradiance = poa_irradiance.sum()

        # Assume a simplified model where energy is proportional to irradiance
        # Calculate energy generated (Wh)
        energy_generated = total_poa_irradiance * facade_area / 1000  # Convert to kWh

        # Apply system losses
        effective_energy_generated = energy_generated * (1 - system_losses / 100)

        st.success(f"Total energy generated by the facade from {study_start_date} to {study_end_date}: {effective_energy_generated:.2f} kWh")

        # Provide feedback on data needs
        st.info("For more accurate calculations, ensure the irradiance data is accurate and up-to-date. Using site-specific data rather than generic data can improve accuracy.")
