import os
import re
import pandas as pd
import hashlib
import requests
import json
from geopy.geocoders import Nominatim
import time
import nbformat

# =============================================================
# Helper functions for data processing and code bloat reduction
# =============================================================

# construct address for geocoding only (don't modify original data)
def construct_geocoding_address(row):
    # Build clean address from original components
    address = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"
    return address

# get lat/lon from address with increased timeout and retry/delay
def get_lat_lon(address, max_retries=3, delay=2):
    geolocator = Nominatim(user_agent="CLEAR-geoapi-2025")
    for attempt in range(max_retries):
        try:
            location = geolocator.geocode(address, timeout=5)
            if location:
                return location.latitude, location.longitude
            else:
                return None, None
        except Exception as e:
            print(f"Error geocoding {address} (attempt {attempt+1}): {e}")
            time.sleep(delay)
    return None, None

# generate short unique ID based on ['hospital'] + full composite address (base36, 8 chars)
def generate_short_id(row):
    full_address = construct_geocoding_address(row)
    unique_string = f"{row['name']}_{full_address}"
    hash_int = int(hashlib.md5(unique_string.encode()).hexdigest(), 16)
    short_id = base36encode(hash_int)[:8]
    return short_id

# base36 encoding for shorter IDs
def base36encode(number):
    chars = '0123456789abcdefghijklmnopqrstuvwxyz'
    if number == 0:
        return '0'
    result = ''
    while number > 0:
        number, i = divmod(number, 36)
        result = chars[i] + result
    return result

# Add lat/lon and short_id to dataframe, set json_path to be '/data/prices/['state']/['id'].json'
def update_dataframe(df, filename='hospitals.csv'):
    
    # Get absolute path to hospitals.csv
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
    hospitals_csv = os.path.join(data_dir, 'hospitals.csv')

    # Don't modify the address column - just use it for geocoding
    def lat_lon_with_delay(row):
        geocoding_address = construct_geocoding_address(row)
        lat, lon = get_lat_lon(geocoding_address)
        time.sleep(1)  # 1 second delay per request
        return pd.Series([lat, lon])
    
    df[['lat', 'lon']] = df.apply(lat_lon_with_delay, axis=1)
    df['id'] = df.apply(generate_short_id, axis=1)
    df['json_path'] = df.apply(lambda row: f"docs/data/prices/{row['state']}/{row['id']}.json", axis=1)
    df.to_csv(hospitals_csv, index=False)

    return


# Function to update hospitals.csv with a new hospital entry
def add_hospital_entry(hospital_dict, filename='hospitals.csv'):

    """Add a new hospital entry to hospitals.csv if it doesn't already exist.
    hospital_dict should contain keys: 'hospital_name', 'address', 'city_name', 'state_name', 'zip_code'
    
    Returns: hospitals_df so it can be used immediately if needed.

    """

    # Get absolute path to hospitals.csv
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
    hospitals_csv = os.path.join(data_dir, 'hospitals.csv')

    # Load existing hospitals.csv
    hospitals_df = pd.read_csv(hospitals_csv)

    # update hospitals_df with new entry if it doesn't already exist
    if hospitals_df[
        (hospitals_df['name'] == hospital_dict['hospital_name']) &
        (hospitals_df['state'] == hospital_dict['state_name']) &
        (hospitals_df['city'] == hospital_dict['city_name'])
    ].empty:
        
        new_entry = {
            'name': hospital_dict['hospital_name'],
            'address': hospital_dict['address'],
            'city': hospital_dict['city_name'],
            'state': hospital_dict['state_name'],
            'zip': hospital_dict['zip_code']
        }

        hospitals_df = pd.concat([hospitals_df, pd.DataFrame([new_entry])], ignore_index=True)
        hospitals_df.to_csv(hospitals_csv, index=False)  # Save updated CSV
        print(f"Added new hospital entry for '{hospital_dict['hospital_name']}' to hospitals.csv")

        # now run the update_dataframe function to add lat/lon, id, and json_path
        update_dataframe(hospitals_df)
    
    return hospitals_df