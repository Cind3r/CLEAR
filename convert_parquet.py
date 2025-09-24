#!/usr/bin/env python3
"""
Convert large parquet files to web-friendly formats for the CLEAR project.

This script provides several strategies for handling GB-scale parquet files:
1. Split into smaller chunks by state/region
2. Create searchable indexes 
3. Convert to compressed JSON with search capability
4. Create a simple API server for querying
"""

import pandas as pd
import json
import os
from pathlib import Path
import argparse
import re

def chunk_parquet_by_state(input_file, output_dir, chunk_size=10000):
    """Split large parquet into smaller chunks."""
    print(f"Reading {input_file}...")
    df = pd.read_parquet(input_file)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Split into chunks
    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i:i+chunk_size]
        chunk_file = os.path.join(output_dir, f"chunk_{i//chunk_size:04d}.parquet")
        chunk.to_parquet(chunk_file, index=False)
        print(f"Created chunk: {chunk_file} ({len(chunk)} rows)")

def create_searchable_index(input_file, output_file):
    """Create a searchable index of all procedures."""
    print(f"Creating searchable index from {input_file}...")
    df = pd.read_parquet(input_file)
    
    # Select only the columns we need for search
    search_cols = ['description', 'code_1', 'estimated_amount', 
                   'standard_charge_min', 'standard_charge_max']
    
    # Filter out rows with missing descriptions
    df_filtered = df[search_cols].dropna(subset=['description'])
    
    # Convert to JSON for web use
    records = df_filtered.to_dict('records')
    
    with open(output_file, 'w') as f:
        json.dump(records, f, indent=2)
    
    print(f"Created searchable index: {output_file} ({len(records)} procedures)")

def create_compressed_chunks(input_file, output_dir, procedures_per_chunk=1000):
    """Create compressed JSON chunks for web loading."""
    print(f"Creating compressed chunks from {input_file}...")
    df = pd.read_parquet(input_file)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Select columns and clean data
    search_cols = ['description', 'code_1', 'estimated_amount', 
                   'standard_charge_min', 'standard_charge_max']
    df_clean = df[search_cols].dropna(subset=['description'])
    
    # Create chunks
    for i in range(0, len(df_clean), procedures_per_chunk):
        chunk = df_clean.iloc[i:i+procedures_per_chunk]
        chunk_data = chunk.to_dict('records')
        
        chunk_file = os.path.join(output_dir, f"procedures_{i//procedures_per_chunk:04d}.json")
        with open(chunk_file, 'w') as f:
            json.dump(chunk_data, f, separators=(',', ':'))  # Compact JSON
        
        print(f"Created chunk: {chunk_file} ({len(chunk_data)} procedures)")

def create_api_server_script(output_file):
    """Create a simple Python API server for querying parquet files."""
    api_code = '''#!/usr/bin/env python3
"""
Simple API server for querying hospital charge master data.
Usage: python api_server.py
Then access: http://localhost:8080/search?q=MRI&hospital=duke
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import pandas as pd
import json
import re
import os

class DataQueryHandler(BaseHTTPRequestHandler):
    # Load data once at startup
    data_cache = {}
    
    @classmethod
    def load_hospital_data(cls, hospital_id):
        """Load hospital data on demand."""
        if hospital_id in cls.data_cache:
            return cls.data_cache[hospital_id]
        
        # Look for parquet file
        parquet_file = f"data/prices/{hospital_id}.parquet"
        if os.path.exists(parquet_file):
            df = pd.read_parquet(parquet_file)
            cls.data_cache[hospital_id] = df
            return df
        return None
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/search':
            self.handle_search(parsed.query)
        else:
            self.send_error(404)
    
    def handle_search(self, query_string):
        params = parse_qs(query_string)
        search_term = params.get('q', [''])[0]
        hospital_id = params.get('hospital', [''])[0]
        
        if not search_term or not hospital_id:
            self.send_json_response({"error": "Missing q or hospital parameter"})
            return
        
        # Load hospital data
        df = self.load_hospital_data(hospital_id)
        if df is None:
            self.send_json_response({"error": f"Hospital {hospital_id} not found"})
            return
        
        # Search
        regex = re.compile(search_term, re.IGNORECASE)
        matches = df[df['description'].str.contains(search_term, case=False, na=False)]
        
        # Limit results and convert to dict
        results = matches.head(50)[['description', 'code_1', 'estimated_amount', 
                                  'standard_charge_min', 'standard_charge_max']].to_dict('records')
        
        self.send_json_response({"results": results, "count": len(results)})
    
    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')  # Enable CORS
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

if __name__ == '__main__':
    server = HTTPServer(('localhost', 8080), DataQueryHandler)
    print("API server running at http://localhost:8080")
    print("Example: http://localhost:8080/search?q=MRI&hospital=duke")
    server.serve_forever()
'''
    
    with open(output_file, 'w') as f:
        f.write(api_code)
    
    print(f"Created API server script: {output_file}")
    print("Run with: python api_server.py")

def main():
    parser = argparse.ArgumentParser(description='Convert parquet files for web use')
    parser.add_argument('command', choices=['chunk', 'index', 'compress', 'api'], 
                       help='Operation to perform')
    parser.add_argument('--input', required=True, help='Input parquet file')
    parser.add_argument('--output', required=True, help='Output directory or file')
    parser.add_argument('--chunk-size', type=int, default=10000, 
                       help='Rows per chunk (default: 10000)')
    
    args = parser.parse_args()
    
    if args.command == 'chunk':
        chunk_parquet_by_state(args.input, args.output, args.chunk_size)
    elif args.command == 'index':
        create_searchable_index(args.input, args.output)
    elif args.command == 'compress':
        create_compressed_chunks(args.input, args.output)
    elif args.command == 'api':
        create_api_server_script(args.output)

if __name__ == '__main__':
    main()