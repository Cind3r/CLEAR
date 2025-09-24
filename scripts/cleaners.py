import pandas as pd
import numpy as np

# Cleaning function for DUKE UNIVERSITY HOSPITAL
def clean_dataframe_for_parquet(df):
    df_clean = df.copy()
    
    # Convert numeric columns that are stored as strings
    numeric_columns = ['modifiers']  # Add other numeric column names here
    
    for col in numeric_columns:
        if col in df_clean.columns:
            # Convert to numeric, setting errors='coerce' to handle non-numeric values
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    
    return df_clean

