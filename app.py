import streamlit as st
import pvlib
import pandas as pd
import requests
from datetime import datetime
from io import StringIO

# Function to fetch TMY data from NSRDB
def fetch_nsrdb_tmy(api_key, latitude, longitude, full_name, email, affiliation):
    url = (
        f"https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-tmy-download.csv?"
        f"api_key={api_key}&lat={latitude}&lon={longitude}&names=tmy-2018&leap_day=false&interval=60&utc=false"
        f"&full_name={full_name}&email={email}&affiliation={affiliation}&mailing_list=false&wkt=POINT({longitude}%20{latitude})"
    )
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = pd.read_csv(StringIO(response.text), skiprows=2)
            return data
        else:
            st.error(f"Error fetching NSRDB data: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Error fetching NSRDB data: {e}")
        return None

# Function to interpolate zero values
def interpolate_zero_values(series):
    return series.replace(0, pd.NA).interpolate(method='linear').fillna(0)

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
api_key = st.text_input("NSRDB API Key", help="Enter your NSRDB API key to fetch data.")
full_name = st.text_input("Full Name", help="Enter your full name for the NSRDB API request.")
email = st.text_input("Email", help="Enter a valid email address for the NSRDB API request.")
affiliation = st.text_input("Affiliation", help="Enter your affiliation for the NSRDB API request.")

# Retrieve and display available PV modules
sam_data = pvlib.pvsystem.retrieve_sam('SandiaMod')
available_modules = list(sam_data.keys())
module_name = st.selectbox("Select PV Module", available_modules, help="Select the PV module from the available list.")
selected_pv_module = sam_data[module_name]

# Retrieve and display available inverters
inverter_data = pvlib.pvsystem.retrieve_sam('CECInverter')
available_inverters = list(inverter_data.keys())
inverter_name = st.selectbox("Select Inverter", available_inverters, help="Select the inverter from the available list.")
selected_inverter = inverter_data[inverter_name]

if st.button("Calculate Energy Generation"):
    # Validate input dates
    if study_start_date >= study_end_date:
        st.error("End date must be after start date.")
    else:
        # Generate time range
        times = pd.date_range(start=study_start_date, end=study_end_date, freq='H', tz='Etc/GMT+0')

        # Fetch TMY data from NSRDB
        if api_key and full_name and email and affiliation:
            nsrdb_data = fetch_nsrdb_tmy(api_key, latitude, longitude, full_name, email, affiliation)
        else:
            st.error("Please enter your NSRDB API key, full name, email, and affiliation.")
            nsrdb_data = None

        if nsrdb_data is not None:
            # Ensure the 'time' column is converted to datetime and set as the index
            try:
                nsrdb_data['time'] = pd.to_datetime(nsrdb_data[['Year', 'Month', 'Day', 'Hour']])
                nsrdb_data = nsrdb_data.set_index('time')
                nsrdb_data = nsrdb_data.tz_localize('Etc/GMT+0')
            except Exception as e:
                st.error(f"Error processing NSRDB time data: {e}")
                st.stop()

            # Sort the index to ensure it is monotonic
            nsrdb_data = nsrdb_data.sort_index()

            # Align NSRDB data to the study period
            try:
                nsrdb_data = nsrdb_data.reindex(times, method='nearest')
            except Exception as e:
                st.error(f"Error reindexing NSRDB data: {e}")
                st.stop()
            
            # Interpolate zero values
            nsrdb_data['DNI'] = interpolate_zero_values(nsrdb_data['DNI'])
            nsrdb_data['GHI'] = interpolate_zero_values(nsrdb_data['GHI'])
            nsrdb_data['DHI'] = interpolate_zero_values(nsrdb_data['DHI'])

            # Check for remaining zero values
            if (nsrdb_data['GHI'] == 0).all() or (nsrdb_data['DNI'] == 0).all() or (nsrdb_data['DHI'] == 0).all():
                st.warning("Irradiance values (GHI, DNI, DHI) contain zeros. This may affect the accuracy of the calculations.")
                margin_of_error = 20  # Example margin of error in percentage
                st.warning(f"Proceeding with the calculation may introduce a margin of error of approximately {margin_of_error}%.")

            # Debug: Ensure nsrdb_data index is sorted and aligned
            st.write("**NSRDB Data Head**")
            st.write("This table displays the head (first few rows) of the Typical Meteorological Year (TMY) data fetched from the NSRDB database. It provides an overview of the meteorological data for the specified location and study period, including parameters like direct normal irradiance (DNI), global horizontal irradiance (GHI), diffuse horizontal irradiance (DHI), ambient temperature (temp_air), and wind speed.")
            st.write(nsrdb_data.head())

            # Get solar position
            solar_position = pvlib.solarposition.get_solarposition(times, latitude, longitude)

            # Get irradiance data from NSRDB
            dni = nsrdb_data['DNI']
            ghi = nsrdb_data['GHI']
            dhi = nsrdb_data['DHI']
            temp_air = nsrdb_data['Temperature']
            wind_speed = nsrdb_data['Wind Speed']
            
            # Debug: Ensure inputs are Series with matching indices
            st.write("**DNI Head**")
            st.write("This table shows the head of the Direct Normal Irradiance (DNI) values extracted from the NSRDB data. DNI represents the amount of solar radiation received per unit area by a surface that is always held perpendicular (or normal) to the rays that come directly from the sun. It's crucial for calculating the irradiance on the facade.")
            st.write(dni.head())

            st.write("**Temp Air Head**")
            st.write("This table presents the head of the ambient temperature values (Temperature) from the NSRDB data. Ambient temperature is used to calculate the cell temperature of the PV modules, which affects their efficiency and power output.")
            st.write(temp_air.head())

            st.write("**Wind Speed Head**")
            st.write("This table displays the head of the wind speed values from the NSRDB data. Wind speed is also used in calculating the cell temperature. Higher wind speeds can help cool the PV modules, potentially increasing their efficiency.")
            st.write(wind_speed.head())

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
            st.write("**Irradiance Head**")
            st.write("This table shows the head of the irradiance values calculated on the facade. It includes components like direct, diffuse, and global irradiance on the plane of the array (POA). These values are critical for determining the total solar energy incident on the facade.")
            st.write(irradiance.head())

            # Ensure inputs are compatible for cell temperature calculation
            poa_irradiance = irradiance['poa_global']

            # Debug: Check poa_irradiance values
            st.write("**POA Irradiance Head**")
            st.write("This table presents the head of the Plane of Array (POA) irradiance values. POA irradiance is the total irradiance received by the tilted surface (the facade in this case). It combines direct, diffuse, and reflected irradiance components and is used to calculate the energy production of the PV modules.")
            st.write(poa_irradiance.head())

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
            st.write("**Cell Temperature Head**")
            st.write("This table displays the head of the cell temperature values calculated using the Sandia temperature model. Cell temperature significantly affects the performance and efficiency of PV modules. This table helps verify that the temperature calculations are correctly applied.")
            st.write(cell_temperature.head())

            # Create PV system with selected module
            pv_system = pvlib.pvsystem.PVSystem(module_parameters=selected_pv_module, inverter_parameters=selected_inverter)

            # Calculate the DC power output
            try:
                dc_power = pv_system.sapm(pd.Series(poa_irradiance.values, index=times), cell_temperature)
                dc_power_output = dc_power['p_mp']
            except Exception as e:
                st.error(f"Error calculating DC power: {e}")
                st.stop()

            # Debug: Check DC power values
            st.write("**DC Power Head**")
            st.write("This table shows the head of the DC power output calculated by the PV modules. It represents the maximum power point (p_mp) of the PV modules.")
            st.write(dc_power_output.head())

            # Convert DC power to AC power using Sandia inverter model
            try:
                ac_power = pvlib.inverter.sandia(dc_power_output, selected_inverter)
            except Exception as e:
                st.error(f"Error calculating AC power: {e}")
                st.stop()

            # Debug: Check AC power values
            st.write("**AC Power Head**")
            st.write("This table displays the head of the AC power output calculated using the Sandia inverter model. It represents the actual usable power after conversion from DC to AC.")
            st.write(ac_power.head())

            # Calculate total energy generated by the facade (Wh)
            energy_generated = ac_power.sum() * facade_area

            # Apply system losses
            effective_energy_generated = energy_generated * (1 - system_losses / 100)

            # Convert to kWh
            energy_generated_kWh = effective_energy_generated / 1000

            st.success(f"Total energy generated by the facade from {study_start_date} to {study_end_date}: {energy_generated_kWh:.2f} kWh")

            # Provide feedback on data needs
            st.info("For more accurate calculations, ensure the following data is accurate and up-to-date: DNI, GHI, DHI, ambient temperature, and wind speed. Using site-specific data rather than generic TMY data can improve accuracy.")
        else:
            st.error("Unable to fetch sufficient data from available sources.")
