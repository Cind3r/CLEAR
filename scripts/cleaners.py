import pandas as pd
import numpy as np
import re
import json

# Enhanced Payer name standardization function
def standardize_payer_name(payer_name):
    """
    Standardize payer names while preserving important distinctions like state-specific plans
    """
    if pd.isna(payer_name) or payer_name == '':
        return payer_name
    
    # Convert to string and strip whitespace
    name = str(payer_name).strip()
    
    # Remove trailing underscores and extra spaces
    name = re.sub(r'_+$', '', name)
    name = re.sub(r'\s+', ' ', name)
    
    # Standardize common insurance company names while preserving state distinctions
    standardization_patterns = [
        # Aetna variations
        (r'\bAETNA\b.*?(?:\[[\d]+\])?', 'AETNA'),
        (r'\bAetna.*?Health\b', 'AETNA'),
        (r'\bAetna.*?Better.*?Health\b', 'AETNA'),
        
        # Cigna variations
        (r'\bCIGNA\b.*?(?:\[[\d]+\])?', 'CIGNA'),
        (r'\bCigna.*?HealthCare\b', 'CIGNA'),
        (r'\bCigna.*?Health.*?Care\b', 'CIGNA'),
        
        # UHC/United variations
        (r'\bUHC\b.*?(?:\[[\d]+\])?', 'UNITED HEALTHCARE'),
        (r'\bUNITED\s+HEALTHCARE\b', 'UNITED HEALTHCARE'),
        (r'\bUNITED\s+HEALTH\s+GROUP\b', 'UNITED HEALTHCARE'),
        (r'\bUNITED\s+MEDICAL\s+RESOURCES.*CONTRACT\b', 'UNITED HEALTHCARE'),
        (r'\bUMR\b.*?(?:\[[\d]+\])?', 'UNITED HEALTHCARE'),
        (r'\bUNITED\s+OF\s+OMAHA\b', 'UNITED OF OMAHA'),  # Different company
        
        # Humana variations
        (r'\bHUMANA\b.*?(?:\[[\d]+\])?', 'HUMANA'),
        (r'\bHumana.*?Inc\b', 'HUMANA'),
        
        # Anthem/BCBS Anthem variations
        (r'\bANTHEM\b.*?(?:\[[\d]+\])?', 'ANTHEM'),
        (r'\bAnthem.*?Blue.*?Cross\b', 'ANTHEM BLUE CROSS'),
        
        # Kaiser variations
        (r'\bKAISER\b.*?(?:\[[\d]+\])?', 'KAISER PERMANENTE'),
        (r'\bKaiser.*?Permanente\b', 'KAISER PERMANENTE'),
        
        # Wellcare variations
        (r'\bWELLCARE\b.*?(?:\[[\d]+\])?', 'WELLCARE'),
        (r'\bWell.*?Care\b', 'WELLCARE'),
        
        # Molina variations
        (r'\bMOLINA\b.*?(?:\[[\d]+\])?', 'MOLINA HEALTHCARE'),
        (r'\bMolina.*?Healthcare\b', 'MOLINA HEALTHCARE'),
        
        # Blue Cross Blue Shield - preserve state distinctions
        (r'\bBlue_Cross_&_Blue_Shield_of_([A-Za-z_]+)_?', r'BLUE CROSS BLUE SHIELD OF \1'),
        (r'\bBLUE\s+CROSS\s+BLUE\s+SHIELD\s+OF\s+([A-Z\s]+)', r'BLUE CROSS BLUE SHIELD OF \1'),
        (r'\bBCBS\s+OF\s+([A-Z\s]+)', r'BLUE CROSS BLUE SHIELD OF \1'),
        (r'\bBCBS\b', 'BLUE CROSS BLUE SHIELD'),
        
        # Medicare/Medicaid variations
        (r'\bMEDICARE\b.*?(?:\[[\d]+\])?', 'MEDICARE'),
        (r'\bMEDICAID\b.*?(?:\[[\d]+\])?', 'MEDICAID'),
        (r'\bCMS\b.*?(?:\[[\d]+\])?', 'MEDICARE'),
        
        # Tricare variations
        (r'\bTRICARE\b.*?(?:\[[\d]+\])?', 'TRICARE'),
        (r'\bTRI.*?CARE\b', 'TRICARE'),
        
        # Workers Compensation variations
        (r'\bWORKERS.*?COMP\b', 'WORKERS COMPENSATION'),
        (r'\bWORKERS.*?COMPENSATION\b', 'WORKERS COMPENSATION'),
        (r'\bWC\b(?!\s+\d)', 'WORKERS COMPENSATION'),  # Not followed by numbers
        
        # Auto Insurance variations
        (r'\bAUTO\s+INSURANCE\b', 'AUTO INSURANCE'),
        (r'\bMOTOR\s+VEHICLE\b', 'AUTO INSURANCE'),
        (r'\bPIP\b(?!\s+\d)', 'AUTO INSURANCE PIP'),
        
        # Self Pay variations
        (r'\bSELF.*?PAY\b', 'SELF PAY'),
        (r'\bCASH\b(?!\s+\d)', 'SELF PAY'),
        (r'\bSELF.*?INSURED\b', 'SELF PAY'),
        
        # Remove ID numbers in brackets at the end
        (r'\s*\[[\d]+\]\s*$', ''),
        
        # Standardize specific plans and smaller insurers
        (r'\bDUKE\s+PLUS\b', 'DUKE PLUS'),
        (r'\bMAIL\s+HANDLERS\b.*?(?:\[[\d]+\])?', 'MAIL HANDLERS'),
        (r'\bNALC\s+HEALTH\s+BENEFIT\s+PLAN\b.*?(?:\[[\d]+\])?', 'NALC HEALTH BENEFIT PLAN'),
        (r'\bFIRST\s+HEALTH\b.*?(?:\[[\d]+\])?', 'FIRST HEALTH'),
        (r'\bGOLDEN\s+RULE\s+INSURANCE\s+COMPANY\b.*?(?:\[[\d]+\])?', 'GOLDEN RULE INSURANCE'),
        (r'\bOXFORD\s+HEALTH\s+PLANS\b.*?(?:\[[\d]+\])?', 'OXFORD HEALTH PLANS'),
        (r'\bHEALTH\s+NET\b.*?(?:\[[\d]+\])?', 'HEALTH NET'),
        (r'\bAMBETTER\b.*?(?:\[[\d]+\])?', 'AMBETTER'),
        (r'\bCENTENE\b.*?(?:\[[\d]+\])?', 'CENTENE'),
        
        # Federal Employee plans
        (r'\bFEHB\b', 'FEDERAL EMPLOYEE HEALTH BENEFITS'),
        (r'\bFEDERAL\s+EMPLOYEE.*?HEALTH.*?BENEFITS\b', 'FEDERAL EMPLOYEE HEALTH BENEFITS'),
        (r'\bGEHA\b', 'GOVERNMENT EMPLOYEES HEALTH ASSOCIATION'),
        
        # Convert underscores to spaces for better readability
        (r'_', ' '),
        
        # Clean up multiple spaces
        (r'\s+', ' '),
        
        # Fix common OCR/data entry errors
        (r'\b0\b', 'O'),  # Replace standalone 0 with O
        (r'\bl\b', 'I'),  # Replace standalone l with I
    ]
    
    # Apply standardization patterns
    for pattern, replacement in standardization_patterns:
        name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
    
    return name.strip().upper()

# Also create a function to apply standardization to actual data
def apply_payer_standardization_to_json(json_file_path):
    """
    Apply payer standardization to a JSON file and return the modified dataframe
    """
    df = pd.read_json(json_file_path, dtype=str)

    if 'payer_name' in df.columns:
        print(f"Standardizing payer names in {json_file_path}")
        df['payer_name'] = df['payer_name'].apply(standardize_payer_name)
        
        # Show before/after unique counts
        print(f"Unique payer names after standardization: {df['payer_name'].nunique()}")
    
    return df

def transform_wide_to_long_format(df, verbose=False):
    """
    Transform UNC Rex wide format (one row per code with payer columns) 
    to long format (multiple rows per code, one per payer/plan)
    
    Args:
        df: Input DataFrame in wide format
        verbose: If True, prints detailed transformation statistics
    """
    import re
    
    # Print original shape
    original_rows, original_cols = df.shape
    if verbose:
        print(f"Original DataFrame shape: {original_rows} rows × {original_cols} columns")
    
    # First, let's identify the base columns we want to keep
    base_columns = [
        'description', 
        'code|1', 
        'code|1|type', 
        'code|2', 
        'code|2|type', 
        'code|3', 
        'code|3|type',
        'code|4',
        'code|4|type',
        'billing_class', 'setting',
        'drug_unit_of_measurement', 'drug_type_of_measurement', 'modifiers',
        'standard_charge|gross', 'standard_charge|discounted_cash', 
        'standard_charge|min', 'standard_charge|max', 'estimated_amount', 'additional_generic_notes'
    ]
    
    # Keep only base columns that actually exist in the dataframe
    available_base_columns = [col for col in base_columns if col in df.columns]
    if verbose:
        print(f"Available base columns: {len(available_base_columns)} out of {len(base_columns)} possible")
    
    # Find all payer-specific column groups using regex
    payer_pattern = re.compile(r'(standard_charge|estimated_amount|additional_payer_notes)\|([^|]+)\|([^|]+)\|(.+)')
    estimated_amount_pattern = re.compile(r'estimated_amount\|([^|]+)\|([^|]+)$')
    
    payer_columns = {}
    payer_specific_cols = []
    
    for col in df.columns:
        match = payer_pattern.match(col)
        estimated_match = estimated_amount_pattern.match(col)
        
        if match:
            payer_specific_cols.append(col)
            metric_type, payer, plan, field = match.groups()
            payer_plan_key = f"{payer}|{plan}"
            
            if payer_plan_key not in payer_columns:
                payer_columns[payer_plan_key] = {
                    'payer_name': payer,
                    'plan_name': plan,
                    'columns': {}
                }
            
            # Map the field to standardized column names
            if field == 'negotiated_dollar':
                payer_columns[payer_plan_key]['columns']['standard_charge_dollar'] = col
            elif field == 'negotiated_percentage':
                payer_columns[payer_plan_key]['columns']['standard_charge_percentage'] = col
            elif field == 'negotiated_algorithm':
                payer_columns[payer_plan_key]['columns']['standard_charge_algorithm'] = col
            elif field == 'methodology':
                payer_columns[payer_plan_key]['columns']['methodology'] = col
            elif metric_type == 'additional_payer_notes':
                payer_columns[payer_plan_key]['columns']['additional_payer_notes'] = col
                
        elif estimated_match:
            payer_specific_cols.append(col)
            # Handle estimated_amount columns that don't have a field suffix
            payer, plan = estimated_match.groups()
            payer_plan_key = f"{payer}|{plan}"
            
            if payer_plan_key not in payer_columns:
                payer_columns[payer_plan_key] = {
                    'payer_name': payer,
                    'plan_name': plan,
                    'columns': {}
                }
            
            payer_columns[payer_plan_key]['columns']['estimated_amount'] = col
    
    if verbose:
        print(f"Found {len(payer_specific_cols)} payer-specific columns")
        print(f"Found {len(payer_columns)} unique payer/plan combinations")
    
    # Calculate columns that will be dropped
    standard_charge_cols = [col for col in df.columns if col.startswith('standard_charge|') and col in ['standard_charge|gross', 'standard_charge|discounted_cash', 'standard_charge|min', 'standard_charge|max']]
    kept_cols = len(available_base_columns) + len(standard_charge_cols) + 2  # +2 for payer_name and plan_name
    # Add columns that will be created from payer-specific data
    potential_payer_cols = set()
    for payer_info in payer_columns.values():
        potential_payer_cols.update(payer_info['columns'].keys())
    kept_cols += len(potential_payer_cols)
    
    columns_dropped = original_cols - kept_cols
    if verbose:
        print(f"Columns being dropped: {columns_dropped}")
        print(f"Expected columns in result: {kept_cols}")
    
    # Create list to store transformed rows
    transformed_rows = []
    
    # Process each row in the original dataframe
    for _, row in df.iterrows():
        # Extract base information for this code
        base_info = {}
        for col in available_base_columns:
            base_info[col.replace('|', '_')] = row[col]
        
        # Add standard charges that apply to all payers
        base_info['standard_charge_gross'] = row.get('standard_charge|gross', None)
        base_info['standard_charge_discounted_cash'] = row.get('standard_charge|discounted_cash', None)
        base_info['standard_charge_min'] = row.get('standard_charge|min', None)
        base_info['standard_charge_max'] = row.get('standard_charge|max', None)
        
        # Create a row for each payer/plan combination
        for payer_plan_key, payer_info in payer_columns.items():
            # Start with base information
            new_row = base_info.copy()
            
            # Add payer and plan names
            new_row['payer_name'] = payer_info['payer_name']
            new_row['plan_name'] = payer_info['plan_name']
            
            # Add payer-specific values
            for standard_col, original_col in payer_info['columns'].items():
                new_row[standard_col] = row.get(original_col, None)
            
            # Only add rows that have some meaningful data (not all null payer-specific values)
            payer_specific_values = [new_row.get(col) for col in ['standard_charge_dollar', 'standard_charge_percentage', 'estimated_amount']]
            if any(pd.notna(val) and val != '' for val in payer_specific_values):
                transformed_rows.append(new_row)
    
    # Create new dataframe from transformed rows
    if transformed_rows:
        result_df = pd.DataFrame(transformed_rows)
        final_rows, final_cols = result_df.shape
        if verbose:
            print(f"Final DataFrame shape: {final_rows} rows × {final_cols} columns")
            
            # Calculate transformation metrics
            row_multiplication_factor = final_rows / original_rows if original_rows > 0 else 0
            print(f"Row multiplication factor: {row_multiplication_factor:.2f}x (from {original_rows} to {final_rows})")
            print(f"Actual columns dropped: {original_cols - final_cols}")
            
            # Mathematical validation
            total_data_points_original = original_rows * original_cols
            total_data_points_final = final_rows * final_cols
            data_efficiency = total_data_points_final / total_data_points_original if total_data_points_original > 0 else 0
            print(f"Data efficiency: {data_efficiency:.2f} (final data points / original data points)")
            print(f"Original total data points: {total_data_points_original:,}")
            print(f"Final total data points: {total_data_points_final:,}")
        
        return result_df
    else:
        print("No transformed rows created - returning empty DataFrame")
        return pd.DataFrame()

# ==============================================================
# DEPRECIATED
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

