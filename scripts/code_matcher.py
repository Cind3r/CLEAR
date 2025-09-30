import pandas as pd
import re
import os

# =============================================================
# CSV FILE PATHS TO HCPCS/CPT CODE MAPPINGS
# =============================================================

# For now ignore master file as it uses fewer codes than the individual files

hcpcs_filename = 'hcpcs_lvl2_top_200_codes_2024.csv'
lab_filename = 'lab_top_100_codes_2024.csv'
cpt_filename = 'cpt_lvl1_top_200_codes_2024.csv'
master_filename = 'top_codes_master_dictionary_v4.csv'

# =============================================================

# helper func to load the csv files
def _loader():
    try:
        # Get absolute path to docs/data directory
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
        
        # Load CSV files
        hcpcs_codes = pd.read_csv(os.path.join(data_dir, hcpcs_filename))
        lab_codes = pd.read_csv(os.path.join(data_dir, lab_filename))
        cpt_codes = pd.read_csv(os.path.join(data_dir, cpt_filename))
        all_codes = pd.read_csv(os.path.join(data_dir, master_filename))

    except FileNotFoundError as e:
        print(f"Error: {e}. Please ensure the CSV files are in the 'docs/data' directory.")
        exit(1)

    return hcpcs_codes, lab_codes, cpt_codes, all_codes

# Main function to get matches
def get_matches(df, verbose=False, cols_to_drop=None):

    """
    Identify and extract rows from the input DataFrame that match HCPCS, Lab, or CPT codes.
    Parameters:
    - df (pd.DataFrame): Input DataFrame containing code columns.
    - verbose (bool): If True, print detailed processing information.
    - cols_to_drop (list): List of columns to drop from the final output DataFrame. If None, a default list is used.
    Returns:
    - pd.DataFrame: DataFrame containing rows with matched codes, duplicates dropped, with specified columns dropped.
    """

    hcpcs_codes, lab_codes, cpt_codes, all_codes = _loader()

    if cols_to_drop is None:
        cols_to_drop = [
            'billing_class',
            'drug_unit_of_measurement',
            'drug_type_of_measurement',
            'modifiers',
            'standard_charge_algorithm',
            'additional_generic_notes', 
            'methodology'
            ]

    if verbose:
        print("Loaded the following code sets:")
        print(f"HCPCS Codes: {hcpcs_codes.shape[0]} entries")
        print(f"Lab Codes: {lab_codes.shape[0]} entries")
        print(f"CPT Codes: {cpt_codes.shape[0]} entries")
        print(f"All Codes: {all_codes.shape[0]} entries")

    # Check df for columns containing 'code' but not 'type'
    code_columns = [col for col in df.columns if 'code' in col.lower() and 'type' not in col.lower()]
    if verbose:
        print(f"Identified code columns: {code_columns}")
        # check to make sure code columns are in the form 'code_#'
        for col in code_columns:
            if not re.match(r'code_\d+$', col):
                print(f"Warning: Column '{col}' does not match expected format 'code_#'.")
                
                # Change '|' to '_' in column name if present
                if '|' in col:
                    new_col = col.replace('|', '_')
                    df = df.rename(columns={col: new_col})
                    print(f"Renamed column '{col}' to '{new_col}'.")
                    
                    # Also rename corresponding type column
                    type_col = f"{col}|type"
                    new_type_col = f"{new_col}_type"
                    
                    df[new_type_col] = df[type_col]
                    df = df.drop(columns=[type_col])
                    print(f"Renamed column '{type_col}' to '{new_type_col}'.")

                    # Update code_columns list
                    code_columns[code_columns.index(col)] = new_col

    if not code_columns:
        print("No code columns found in the DataFrame.")
        return pd.DataFrame()  # Return empty DataFrame if no code columns found

    # Check code columns for matches in each code set, return rows with matches for each set
    matched_dfs = []
    for col in code_columns:

        hcpcs_matches = df[df[col].isin(hcpcs_codes['HCPCS Code'])].copy()
        lab_matches = df[df[col].isin(lab_codes['HCPCS Code'])].copy()
        cpt_matches = df[df[col].isin(cpt_codes['HCPCS Code'])].copy()

        if verbose:
            print(f"Column '{col}': Found {hcpcs_matches.shape[0]} HCPCS matches, {lab_matches.shape[0]} Lab matches, {cpt_matches.shape[0]} CPT matches.")
        
        if hcpcs_matches.empty and lab_matches.empty and cpt_matches.empty:
            if verbose:
                print(f"No matches found in column '{col}'.")
            continue  # Skip to next column if no matches found
       
       # Add 'code' and 'type' columns to each matches DataFrame
        if verbose:
           print(f"Reassigning {col} to 'code' and '{col}_type' to 'type' for non-empty matches DataFrames.")
        if not hcpcs_matches.empty:
            hcpcs_matches['code'] = hcpcs_matches[col]
            hcpcs_matches['type'] = hcpcs_matches[f'{col}_type']
        if not lab_matches.empty:
            lab_matches['code'] = lab_matches[col]
            lab_matches['type'] = lab_matches[f'{col}_type']
        if not cpt_matches.empty:
            cpt_matches['code'] = cpt_matches[col]
            cpt_matches['type'] = cpt_matches[f'{col}_type']

        # Filter out empty DataFrames
        matches = [df for df in [hcpcs_matches, lab_matches, cpt_matches] if not df.empty]

        # Combine matches into a single DataFrame
        combined_matches = pd.concat(matches, axis=0)
        if verbose:
            print(f"Column '{col}': Combined matches shape: {combined_matches.shape}")

        # Check duplicates - prioritize rows with non-NaN estimated_amount
        # Check duplicates based on key columns, keeping rows with non-NaN estimated_amount
        key_cols = ['code', 'payer_name', 'plan_name', 'description']  # adjust as needed
        combined_matches = combined_matches.sort_values('estimated_amount', na_position='last')
        combined_matches = combined_matches.drop_duplicates(subset=key_cols)

        if verbose:
            print(f"Column '{col}': Unique matches after dropping duplicates: {combined_matches.shape[0]}")
        
        # Append to list of matched DataFrames
        matched_dfs.append(combined_matches)

        # Delete temporary DataFrames to free memory then loop to next column
        del hcpcs_matches, lab_matches, cpt_matches, combined_matches

    # Merge all matched DataFrames into a single DataFrame
    merged_df = pd.concat(matched_dfs, axis=0)

    # Remove code_# and code_#_type columns but keep plain 'code' column, and column containing RC codes if present
    # First check which code_type_# cols contain 'RC' string
    rc_code_type_cols = [col for col in merged_df.columns if re.match(r'code_\d+_type$', col) and 'RC' in merged_df[col].values]
    
    if rc_code_type_cols:
        # Find the code_# col that corresponds to the RC code_type col
        rc_code_cols = [col.replace('_type', '') for col in rc_code_type_cols]
        
        if verbose:
            print(f"Found RC code columns: {rc_code_cols}")
        
        # Rename the RC code column to 'rc_code'
        for rc_col in rc_code_cols:
            merged_df = merged_df.rename(columns={rc_col: 'rc_code'})
        
        # Drop all code_# and code_#_type columns
        code_type_cols = [col for col in merged_df.columns if re.match(r'code_\d+(_type)?$', col)]
        merged_df = merged_df.drop(columns=code_type_cols, errors='ignore')
    else:
        # No RC codes found, drop all code_# and code_#_type columns
        code_type_cols = [col for col in merged_df.columns if re.match(r'code_\d+(_type)?$', col)]
        merged_df = merged_df.drop(columns=code_type_cols, errors='ignore')
    
    if verbose:
        print(f"Dropped code/type columns: {code_type_cols}")
        print(f"Merged DataFrame shape before dropping duplicates: {merged_df.shape}")
    
    merged_df = merged_df.drop_duplicates()

    if verbose:
        print(f"Merged DataFrame shape after dropping duplicates: {merged_df.shape}")
    
    # Check for NaN values in payer_name column
    if 'payer_name' in merged_df.columns:
        nan_count = merged_df['payer_name'].isna().sum()
        
        if nan_count > 0 and verbose:
            print(f"Warning: 'payer_name' column contains {nan_count} NaN values.")
            print("Dropping rows with NaN 'payer_name'.")
            
            merged_df = merged_df[merged_df['payer_name'].notna()]
           
            if verbose:
                print(f"Shape after dropping NaN 'payer_name': {merged_df.shape}")
            
            if merged_df.empty:
                print("Error: No matches found after dropping NaN 'payer_name'. Returning empty DataFrame.")   
                return pd.DataFrame()  # Return empty DataFrame if no matches found
        else:
            print("No NaN values found in 'payer_name' column...")

    if merged_df.empty:
        print("No matches found across all code columns. Returning empty DataFrame.")
        return pd.DataFrame()  # Return empty DataFrame if no matches found
    else:
        if verbose:
            print(f"Total unique matched codes: {merged_df['code'].nunique()}")
            print(f"Matched DataFrame shape: {merged_df.shape}")

    # now drop any excess columns that aren't needed
    merged_df = merged_df.drop(columns=cols_to_drop, errors='ignore')
    if verbose:
        print(f"Dropped unnecessary columns: {cols_to_drop}")
        print(f"Final matched DataFrame shape: {merged_df.shape}")

    return merged_df
