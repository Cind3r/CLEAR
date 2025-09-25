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

