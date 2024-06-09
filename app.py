import streamlit as st
import pvlib
import pandas as pd
from datetime import datetime

# Function to fetch TMY data from PVGIS
def fetch_tmy_data(latitude, longitude):
    try:
        tmy_data = pvlib.iotools.get_pvgis_tmy(latitude, longitude)
        return tmy_data[0]  # Return only the TMY data part
    except Exception as e:
        st.error(f"Error fetching TMY data: {e}")
        return None

# Function to check compatibility between PV module and inverter
def check_compatibility(pv_module, inverter):
    max_power = pv_module['Pmp']
    max_voltage = pv_module['Vmpo']
    max_current = pv_module['Impo']
    inverter_voltage = inverter['Vac']
    inverter_power = inverter['Pdco']
    
    if max_voltage > inverter_voltage:
        st.error("Selected PV module's voltage exceeds the inverter's voltage rating.")
        return False
    if max_power > inverter_power:
        st.error("Selected PV module's power exceeds the inverter's power rating.")
        return False
    if max_current > inverter['Idco']:
        st.error("Selected PV module's current exceeds the inverter's current rating.")
        return False
    
    return True

# Streamlit app interface
st.title("Facade Energy Generation Calculator")

st.write("""
This tool allows you to calculate the potential energy generation from a building facade based on user inputs such as facade azimuth, location, study time, and facade area. 
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

# Retrieve and display available PV modules
sam_data = pvlib.pvsystem.retrieve_sam('SandiaMod')
available_modules = list(sam_data.keys())
module_name = st.selectbox("Select PV Module", available_modules, help="Select the PV module from the available list.")

# Retrieve and display available inverters
inverter_data = pvlib.pvsystem.retrieve_sam('CECInverter')
available_inverters = list(inverter_data.keys())
inverter_name = st.selectbox("Select Inverter", available_inverters, help="Select the inverter from the available list.")

if st.button("Calculate Energy Generation"):
    # Validate input dates
    if study_start_date >= study_end_date:
        st.error("End date must be after start date.")
    else:
        # Generate time range
        times = pd.date_range(start=study_start_date, end=study_end_date, freq='H', tz='Etc/GMT+0')

        # Fetch TMY data
        tmy_data = fetch_tmy_data(latitude, longitude)
        if tmy_data is not None:
            # Sort the index to ensure it is monotonic
            tmy_data = tmy_data.sort_index()

            # Align TMY data to the study period
            tmy_data = tmy_data.reindex(times, method='nearest')
            
            # Debug: Ensure tmy_data index is sorted and aligned
            st.write("TMY Data Head", tmy_data.head())

            # Get solar position
            solar_position = pvlib.solarposition.get_solarposition(times, latitude, longitude)

            # Get irradiance data from TMY
            dni = tmy_data['dni']
            ghi = tmy_data['ghi']
            dhi = tmy_data['dhi']
            temp_air = tmy_data['temp_air']
            wind_speed = tmy_data['wind_speed']

            # Debug: Ensure inputs are Series with matching indices
            st.write("DNI Head", dni.head())
            st.write("Temp Air Head", temp_air.head())
            st.write("Wind Speed Head", wind_speed.head())

            # Calculate irradiance on the facade
            irradiance = pvlib.irradiance.get_total_irradiance(
                surface_tilt=90,
                surface_azimuth=facade_azimuth,
                solar_zenith=solar_position['apparent_zenith'],
                solar_azimuth=solar_position['azimuth'],
                dni=dni,
                ghi=ghi,
                dhi=dhi
            )

            # Debug: Check irradiance values
            st.write("Irradiance Head", irradiance.head())

            # Select the chosen PV module
            pv_module = sam_data[module_name]
            pv_system = pvlib.pvsystem.PVSystem(module_parameters=pv_module)

            # Ensure inputs are compatible for cell temperature calculation
            poa_irradiance = irradiance['poa_global']

            # Debug: Check poa_irradiance values
            st.write("POA Irradiance Head", poa_irradiance.head())

            # Parameters for the Sandia Cell Temperature Model
            a = -3.47  # Default parameter
            b = -0.0594  # Default parameter
            deltaT = 3  # Default parameter

            # Calculate the cell temperature using the Sandia method
            try:
                cell_temperature = pvlib.temperature.sapm_cell(
                    poa_global=pd.Series(poa_irradiance.values, index=times),
                    temp_air=pd.Series(temp_air.values, index=times),
                    wind_speed=pd.Series(wind_speed.values, index=times),
                    a=a,
                    b=b,
                    deltaT=deltaT
                )
            except Exception as e:
                st.error(f"Error calculating cell temperature: {e}")
                st.stop()

            # Debug: Check cell temperature values
            st.write("Cell Temperature Head", cell_temperature.head())

            # Calculate the DC power output
            try:
                dc_power = pv_system.sapm(pd.Series(poa_irradiance.values, index=times), cell_temperature)
                dc_power_output = dc_power['p_mp']
            except Exception as e:
                st.error(f"Error calculating DC power: {e}")
                st.stop()

            # Debug: Check DC power values
            st.write("DC Power Head", dc_power_output.head())

            # Select the chosen inverter
            inverter = inverter_data[inverter_name]

            # Check compatibility between PV module and inverter
            if not check_compatibility(pv_module, inverter):
                st.stop()

            # Convert DC power to AC power using Sandia inverter model
            try:
                ac_power = pvlib.inverter.sandia(dc_power_output, inverter)
            except Exception as e:
                st.error(f"Error calculating AC power: {e}")
                st.stop()

            # Debug: Check AC power values
            st.write("AC Power Head", ac_power.head())

            # Calculate total energy generated by the facade (Wh)
            energy_generated = ac_power.sum() * facade_area

            # Apply system losses
            effective_energy_generated = energy_generated * (1 - system_losses / 100)

            # Convert to kWh
            energy_generated_kWh = effective_energy_generated / 1000

            st.success(f"Total energy generated by the facade from {study_start_date} to {study_end_date}: {energy_generated_kWh:.2f} kWh")

            # Provide feedback on data needs
            st.info("For more accurate calculations, ensure the following data is accurate and up-to-date: DNI, GHI, DHI, ambient temperature, and wind speed. Using site-specific data rather than generic TMY data can improve accuracy.")
