"""
Enhanced Pricing Reader for Medicare/CMS Pricing Files

This module provides comprehensive functionality to read and parse various Medicare/CMS 
pricing files including ASC, ASP, CLFS, DMEPOS, and PFALL formats. It includes 
anesthesia pricing calculations and code matching capabilities.

Author: Generated for CLEAR Healthcare Price Transparency Project
"""

import pandas as pd
import numpy as np
import os
import re
from typing import Dict, List, Tuple, Optional, Union
import warnings
warnings.filterwarnings('ignore')


class UniversalPricingReader:
    """
    Universal file reader class that intelligently identifies file structures
    and extracts pricing information from various CMS pricing files.
    """
    
    def __init__(self, file_path: str):
        """
        Initialize with a file path and automatically detect file structure.
        
        Args:
            file_path (str): Path to the pricing CSV file
        """
        self.file_path = file_path
        self.filename = os.path.basename(file_path).upper()
        self.df = None
        self.header_row = 0
        self.code_column = None
        self.price_column = None
        self.file_type = self._detect_file_type()
        
    def _detect_file_type(self) -> str:
        """Detect file type based on filename patterns."""
        if 'ASC' in self.filename:
            return 'ASC'
        elif 'ASP' in self.filename:
            return 'ASP'
        elif 'CLFS' in self.filename:
            return 'CLFS'
        elif 'DMEPOS' in self.filename:
            return 'DMEPOS'
        elif 'PFALL' in self.filename:
            return 'PFALL'
        else:
            return 'UNKNOWN'
    
    def _find_header_row(self, df: pd.DataFrame) -> int:
        """
        Intelligently find the header row by looking for common patterns.
        
        Args:
            df (pd.DataFrame): Raw dataframe to analyze
            
        Returns:
            int: Row index containing headers
        """
        # Look for rows containing common pricing file headers
        header_keywords = ['HCPCS', 'CODE', 'PRICE', 'RATE', 'YEAR', 'PAYMENT', 'LIMIT']
        
        for idx, row in df.head(10).iterrows():
            row_str = ' '.join([str(cell).upper() for cell in row if pd.notna(cell)])
            if any(keyword in row_str for keyword in header_keywords):
                return idx
        
        return 0  # Default to first row if no clear header found
    
    def _identify_columns(self, df: pd.DataFrame) -> Tuple[str, str]:
        """
        Identify code and price columns based on file type and content analysis.
        
        Args:
            df (pd.DataFrame): Dataframe with headers
            
        Returns:
            Tuple[str, str]: (code_column_name, price_column_name)
        """
        columns = [str(col).upper() for col in df.columns]
        
        # File-specific column identification
        if self.file_type == 'ASC':
            code_col = next((col for col in df.columns if 'HCPCS' in str(col).upper()), None)
            price_col = next((col for col in df.columns if 'PRICE' in str(col).upper()), None)
            
        elif self.file_type == 'ASP':
            # ASP format: 'HCPCS Code,Short Description,Dosage,Price,...'
            code_col = next((col for col in df.columns if 'HCPCS' in str(col).upper() and 'CODE' in str(col).upper()), None)
            price_col = next((col for col in df.columns if str(col).upper() == 'PRICE'), None)
            # Also try looking for columns by position if name matching fails
            if not code_col and len(df.columns) > 0:
                code_col = df.columns[0]  # First column should be HCPCS Code
            if not price_col and len(df.columns) > 3:
                price_col = df.columns[3]  # Fourth column should be Price
            
        elif self.file_type == 'CLFS':
            # CLFS format: 'HCPCS,MOD,INDICATOR,PRICE,SHORTDESC,...'
            code_col = next((col for col in df.columns if str(col).upper() == 'HCPCS'), None)
            price_col = next((col for col in df.columns if str(col).upper() == 'PRICE'), None)
            
        elif self.file_type == 'DMEPOS':
            code_col = next((col for col in df.columns if col.upper() == 'HCPCS'), None)
            price_col = next((col for col in df.columns if 'PRICE' in str(col).upper() and 'MAX' in str(col).upper()), None)
            
        elif self.file_type == 'PFALL':
            # PFALL has no headers, use positional approach
            if len(df.columns) >= 6:
                code_col = df.columns[3]  # 4th column (0-indexed)
                price_col = df.columns[5]  # 6th column (0-indexed)
            else:
                code_col = df.columns[0]
                price_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        else:
            # Generic fallback - look for common patterns
            code_col = None
            for col in df.columns:
                if any(term in str(col).upper() for term in ['HCPCS', 'CODE', 'CPT']):
                    code_col = col
                    break
            
            price_col = None
            for col in df.columns:
                if any(term in str(col).upper() for term in ['PRICE', 'RATE', 'PAYMENT', 'AMOUNT', 'LIMIT']):
                    price_col = col
                    break
        
        return code_col, price_col
    
    def load_and_parse(self) -> pd.DataFrame:
        """
        Load and parse the pricing file, returning a clean DataFrame.
        
        Returns:
            pd.DataFrame: Cleaned dataframe with 'code' and 'price' columns
        """
        try:
            # Read raw file
            if self.file_type == 'PFALL':
                # PFALL is large and has no headers
                raw_df = pd.read_csv(self.file_path, header=None, dtype=str)
            else:
                raw_df = pd.read_csv(self.file_path, dtype=str)
            
            # Find header row (except for PFALL)
            if self.file_type != 'PFALL':
                self.header_row = self._find_header_row(raw_df)
                
                # Re-read with correct header
                if self.header_row > 0:
                    self.df = pd.read_csv(self.file_path, skiprows=self.header_row, dtype=str)
                else:
                    self.df = raw_df.copy()
            else:
                self.df = raw_df.copy()
            
            # Identify columns
            self.code_column, self.price_column = self._identify_columns(self.df)
            
            if not self.code_column or not self.price_column:
                raise ValueError(f"Could not identify code or price columns in {self.filename}")
            
            # Extract and clean data
            result_df = self.df[[self.code_column, self.price_column]].copy()
            result_df.columns = ['code', 'price']
            
            # Clean the data
            result_df = self._clean_data(result_df)
            
            return result_df
            
        except Exception as e:
            print(f"Error loading {self.filename}: {str(e)}")
            return pd.DataFrame(columns=['code', 'price'])
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize the extracted pricing data.
        
        Args:
            df (pd.DataFrame): Raw extracted data
            
        Returns:
            pd.DataFrame: Cleaned dataframe
        """
        # Remove rows with missing codes or prices
        df = df.dropna(subset=['code', 'price'])
        
        # Clean price column - remove non-numeric characters and convert to float
        df['price'] = df['price'].astype(str).str.replace(r'[^\d.-]', '', regex=True)
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        
        # Remove rows with invalid prices
        df = df.dropna(subset=['price'])
        df = df[df['price'] > 0]
        
        # Clean code column - remove whitespace and standardize
        df['code'] = df['code'].astype(str).str.strip().str.upper()
        
        # Remove empty codes
        df = df[df['code'] != '']
        df = df[df['code'] != 'NAN']
        
        # Remove duplicates, keeping the first occurrence
        df = df.drop_duplicates(subset=['code'], keep='first')
        
        # Add source information
        df['source'] = self.file_type
        df['source_file'] = self.filename
        
        return df.reset_index(drop=True)


class MedicarePricingParser:
    """
    Main parser class that handles all pricing file types and provides 
    unified access to Medicare pricing data.
    """
    
    def __init__(self, pricing_folder: str):
        """
        Initialize with the folder containing pricing files.
        
        Args:
            pricing_folder (str): Path to folder containing pricing CSV files
        """
        self.pricing_folder = pricing_folder
        self.pricing_data = {}
        self.anesthesia_conversion_factor = 21.96  # 2025 CMS Anesthesia Conversion Factor
        
    def parse_asc_pricing(self) -> pd.DataFrame:
        """Parse ASC (Ambulatory Surgery Center) pricing file."""
        asc_file = os.path.join(self.pricing_folder, 'ASC_Pricing.csv')
        if os.path.exists(asc_file):
            reader = UniversalPricingReader(asc_file)
            return reader.load_and_parse()
        return pd.DataFrame(columns=['code', 'price', 'source', 'source_file'])
    
    def parse_asp_pricing(self) -> pd.DataFrame:
        """Parse ASP (Average Sales Price) pricing file."""
        asp_file = os.path.join(self.pricing_folder, 'ASP_Pricing_File_2025.csv')
        if os.path.exists(asp_file):
            reader = UniversalPricingReader(asp_file)
            return reader.load_and_parse()
        return pd.DataFrame(columns=['code', 'price', 'source', 'source_file'])
    
    def parse_clfs_pricing(self) -> pd.DataFrame:
        """Parse CLFS (Clinical Laboratory Fee Schedule) pricing file."""
        clfs_files = [f for f in os.listdir(self.pricing_folder) if 'CLFS' in f.upper() and f.endswith('.csv')]
        if clfs_files:
            clfs_file = os.path.join(self.pricing_folder, clfs_files[0])
            reader = UniversalPricingReader(clfs_file)
            return reader.load_and_parse()
        return pd.DataFrame(columns=['code', 'price', 'source', 'source_file'])
    
    def parse_dmepos_pricing(self) -> pd.DataFrame:
        """Parse DMEPOS (Durable Medical Equipment) pricing file."""
        dmepos_files = [f for f in os.listdir(self.pricing_folder) if 'DMEPOS' in f.upper() and f.endswith('.csv')]
        if dmepos_files:
            dmepos_file = os.path.join(self.pricing_folder, dmepos_files[0])
            reader = UniversalPricingReader(dmepos_file)
            return reader.load_and_parse()
        return pd.DataFrame(columns=['code', 'price', 'source', 'source_file'])
    
    def parse_pfall_pricing(self) -> pd.DataFrame:
        """Parse PFALL (Physician Fee Schedule) pricing file."""
        pfall_files = [f for f in os.listdir(self.pricing_folder) if 'PFALL' in f.upper() and f.endswith('.csv')]
        if pfall_files:
            pfall_file = os.path.join(self.pricing_folder, pfall_files[0])
            reader = UniversalPricingReader(pfall_file)
            return reader.load_and_parse()
        return pd.DataFrame(columns=['code', 'price', 'source', 'source_file'])
    
    def calculate_anesthesia_price(self, base_units: float, time_minutes: float = 68, 
                                 modifier_units: float = 0, gpci_adjustment: float = 1.0) -> float:
        """
        Calculate anesthesia pricing based on CMS formula.
        
        Payment = (Base Units + Time Units + Modifying Units) × Conversion Factor × GPCI
        
        Args:
            base_units (float): Base units for the anesthesia procedure
            time_minutes (float): Time in minutes (default 68 minutes average)
            modifier_units (float): Additional modifying units (default 0)
            gpci_adjustment (float): Geographic Practice Cost Index adjustment (default 1.0)
            
        Returns:
            float: Calculated anesthesia payment amount
        """
        # Time units = time in minutes ÷ 15 (rounded to nearest 0.1)
        time_units = round(time_minutes / 15, 1)
        
        # Total units
        total_units = base_units + time_units + modifier_units
        
        # Calculate payment
        payment = total_units * self.anesthesia_conversion_factor * gpci_adjustment
        
        return round(payment, 2)
    
    def parse_anesthesia_pricing(self, anesthesia_codes: List[str]) -> pd.DataFrame:
        """
        Generate anesthesia pricing for given codes using standard base units.
        
        Note: This is a simplified implementation. In practice, you would need
        the actual CMS Anesthesia Base Units file for accurate base unit values.
        
        Args:
            anesthesia_codes (List[str]): List of anesthesia HCPCS/CPT codes
            
        Returns:
            pd.DataFrame: Dataframe with anesthesia pricing
        """
        # Common anesthesia base units (simplified mapping)
        base_units_mapping = {
            '00100': 5,   # Anesthesia for procedures on salivary glands
            '00102': 5,   # Anesthesia for procedures involving plastic repair of cleft lip
            '00103': 5,   # Anesthesia for reconstructive procedures of eyelid
            '00104': 3,   # Anesthesia for electroconvulsive therapy
            '00120': 5,   # Anesthesia for procedures on external, middle, and inner ear
            '00124': 5,   # Anesthesia for procedures on auditory canal
            '00126': 5,   # Anesthesia for tympanotomy
            '00140': 5,   # Anesthesia for procedures on eye; not otherwise specified
            '00142': 5,   # Anesthesia for procedures on eye; lens surgery
            '00144': 5,   # Anesthesia for procedures on eye; corneal transplant
            '00145': 5,   # Anesthesia for procedures on eye; vitreoretinal surgery
            '00147': 5,   # Anesthesia for procedures on eye; iridectomy
            '00148': 5,   # Anesthesia for procedures on eye; ophthalmic surgery
        }
        
        anesthesia_prices = []
        for code in anesthesia_codes:
            base_units = base_units_mapping.get(code, 5)  # Default to 5 base units
            price = self.calculate_anesthesia_price(base_units)
            
            anesthesia_prices.append({
                'code': code,
                'price': price,
                'source': 'ANESTHESIA',
                'source_file': 'CALCULATED',
                'base_units': base_units,
                'time_minutes': 68,
                'conversion_factor': self.anesthesia_conversion_factor
            })
        
        return pd.DataFrame(anesthesia_prices)
    
    def parse_all_pricing_files(self) -> Dict[str, pd.DataFrame]:
        """
        Parse all pricing files and return a dictionary of dataframes.
        
        Returns:
            Dict[str, pd.DataFrame]: Dictionary mapping source type to pricing dataframe
        """
        print("Parsing all pricing files...")
        
        self.pricing_data['ASC'] = self.parse_asc_pricing()
        print(f"ASC: {len(self.pricing_data['ASC'])} records")
        
        self.pricing_data['ASP'] = self.parse_asp_pricing()
        print(f"ASP: {len(self.pricing_data['ASP'])} records")
        
        self.pricing_data['CLFS'] = self.parse_clfs_pricing()
        print(f"CLFS: {len(self.pricing_data['CLFS'])} records")
        
        self.pricing_data['DMEPOS'] = self.parse_dmepos_pricing()
        print(f"DMEPOS: {len(self.pricing_data['DMEPOS'])} records")
        
        self.pricing_data['PFALL'] = self.parse_pfall_pricing()
        print(f"PFALL: {len(self.pricing_data['PFALL'])} records")
        
        return self.pricing_data


def match_codes_to_pricing(code_dataframes: List[pd.DataFrame], 
                          pricing_folder: str, 
                          output_file: str = 'matched_pricing.csv',
                          include_anesthesia: bool = True) -> pd.DataFrame:
    """
    Main function to match codes from input dataframes to pricing data and output unified CSV.
    
    Args:
        code_dataframes (List[pd.DataFrame]): List of dataframes containing codes to match
        pricing_folder (str): Path to folder containing pricing files
        output_file (str): Output filename for the unified pricing CSV
        include_anesthesia (bool): Whether to include calculated anesthesia pricing
        
    Returns:
        pd.DataFrame: Unified dataframe with matched pricing
    """
    print("Starting code matching process...")
    
    # Initialize parser
    parser = MedicarePricingParser(pricing_folder)
    
    # Parse all pricing files
    all_pricing = parser.parse_all_pricing_files()
    
    # Combine all input codes
    all_codes = []
    for i, df in enumerate(code_dataframes):
        if 'code' in df.columns:
            codes = df['code'].dropna().unique().tolist()
        elif 'HCPCS Code' in df.columns:
            codes = df['HCPCS Code'].dropna().unique().tolist()
        elif 'Code' in df.columns:
            codes = df['Code'].dropna().unique().tolist()
        else:
            # Try to find a column that looks like codes
            for col in df.columns:
                if any(term in col.upper() for term in ['CODE', 'HCPCS', 'CPT']):
                    codes = df[col].dropna().unique().tolist()
                    break
            else:
                print(f"Warning: Could not find code column in dataframe {i}")
                continue
        
        all_codes.extend(codes)
    
    # Remove duplicates and clean codes
    unique_codes = list(set([str(code).strip().upper() for code in all_codes if pd.notna(code)]))
    print(f"Total unique codes to match: {len(unique_codes)}")
    
    # Combine all pricing data
    combined_pricing = []
    for source, pricing_df in all_pricing.items():
        if not pricing_df.empty:
            combined_pricing.append(pricing_df)
    
    if combined_pricing:
        all_pricing_df = pd.concat(combined_pricing, ignore_index=True)
    else:
        all_pricing_df = pd.DataFrame(columns=['code', 'price', 'source', 'source_file'])
    
    # Add anesthesia pricing if requested
    if include_anesthesia:
        anesthesia_codes = [code for code in unique_codes if code.startswith('00')]
        if anesthesia_codes:
            anesthesia_pricing = parser.parse_anesthesia_pricing(anesthesia_codes)
            if not anesthesia_pricing.empty:
                all_pricing_df = pd.concat([all_pricing_df, anesthesia_pricing], ignore_index=True)
    
    # Match codes to pricing
    matched_results = []
    unmatched_codes = []
    
    for code in unique_codes:
        matches = all_pricing_df[all_pricing_df['code'] == code]
        
        if not matches.empty:
            # If multiple matches, prioritize by source hierarchy
            source_priority = {'PFALL': 1, 'ASC': 2, 'CLFS': 3, 'ASP': 4, 'DMEPOS': 5, 'ANESTHESIA': 6}
            matches['priority'] = matches['source'].map(source_priority).fillna(99)
            best_match = matches.loc[matches['priority'].idxmin()]
            
            matched_results.append({
                'code': code,
                'price': best_match['price'],
                'source': best_match['source'],
                'source_file': best_match['source_file']
            })
        else:
            unmatched_codes.append(code)
    
    # Create results dataframe
    results_df = pd.DataFrame(matched_results)
    
    # Report statistics
    print(f"\nMatching Results:")
    print(f"Total codes processed: {len(unique_codes)}")
    print(f"Successfully matched: {len(matched_results)}")
    print(f"Unmatched codes: {len(unmatched_codes)}")
    print(f"Match rate: {len(matched_results)/len(unique_codes)*100:.1f}%")
    
    if results_df.empty:
        print("Warning: No codes were successfully matched to pricing data!")
        results_df = pd.DataFrame(columns=['code', 'price', 'source', 'source_file'])
    else:
        # Show source breakdown
        print(f"\nPricing sources used:")
        source_counts = results_df['source'].value_counts()
        for source, count in source_counts.items():
            print(f"  {source}: {count} codes")
    
    # Save to CSV
    if output_file:
        results_df.to_csv(output_file, index=False)
        print(f"\nResults saved to: {output_file}")
    
    # Save unmatched codes for reference
    if unmatched_codes:
        unmatched_df = pd.DataFrame({'code': unmatched_codes})
        unmatched_file = output_file.replace('.csv', '_unmatched.csv')
        unmatched_df.to_csv(unmatched_file, index=False)
        print(f"Unmatched codes saved to: {unmatched_file}")
    
    return results_df


# Example usage and testing functions
def test_pricing_reader(pricing_folder: str):
    """Test function to validate the pricing reader with sample files."""
    parser = MedicarePricingParser(pricing_folder)
    
    print("Testing individual parsers...")
    
    # Test each parser
    asc_data = parser.parse_asc_pricing()
    print(f"ASC test: {len(asc_data)} records loaded")
    if not asc_data.empty:
        print(f"  Sample: {asc_data.iloc[0]['code']} = ${asc_data.iloc[0]['price']}")
    
    asp_data = parser.parse_asp_pricing()
    print(f"ASP test: {len(asp_data)} records loaded")
    if not asp_data.empty:
        print(f"  Sample: {asp_data.iloc[0]['code']} = ${asp_data.iloc[0]['price']}")
    
    clfs_data = parser.parse_clfs_pricing()
    print(f"CLFS test: {len(clfs_data)} records loaded")
    if not clfs_data.empty:
        print(f"  Sample: {clfs_data.iloc[0]['code']} = ${clfs_data.iloc[0]['price']}")
    
    dmepos_data = parser.parse_dmepos_pricing()
    print(f"DMEPOS test: {len(dmepos_data)} records loaded")
    if not dmepos_data.empty:
        print(f"  Sample: {dmepos_data.iloc[0]['code']} = ${dmepos_data.iloc[0]['price']}")
    
    pfall_data = parser.parse_pfall_pricing()
    print(f"PFALL test: {len(pfall_data)} records loaded")
    if not pfall_data.empty:
        print(f"  Sample: {pfall_data.iloc[0]['code']} = ${pfall_data.iloc[0]['price']}")
    
    # Test anesthesia calculation
    anesthesia_price = parser.calculate_anesthesia_price(base_units=5, time_minutes=68)
    print(f"Anesthesia test: 5 base units + 68 minutes = ${anesthesia_price}")


if __name__ == "__main__":
    # Example usage
    pricing_folder = "../ChargeMaster_Project/pricing_info"
    test_pricing_reader(pricing_folder)