# src/ingestion/historical_loader.py

import pandas as pd
import numpy as np
from pathlib import Path
from src.config import DATA_DIR, WEATHER_RAW_DIR

# --- CONFIGURATION ---
HISTORY_DIR = DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# 1. Map CSV Station Names to your Knowledge Graph IDs
STATION_TO_KG_ID = {
    "ANURADHAPURA": "anuradhapura",
    "BATTICALOA": "batticaloa",
    "COLOMBO": "colombo",
    "GALLE": "galle",
    "HAMBANTOTA": "hambantota",
    "JAFFNA": "jaffna",
    "KATUGASTOTA": "kandy",        # Weather station for Kandy
    "KATUNAYAKA": "katunayake",    # Airport / Negombo area
    "MANNAR": "mannar",
    "NUWARA ELIYA": "nuwara_eliya",
    "POLONNARUWA": "polonnaruwa",
    "PUTTALAM": "puttalam",
    "RATNAPURA": "ratnapura",
    "TRINCOMALEE": "trincomalee",
    # From 'Other Stations'
    "BENTOTA ESTATE": "bentota",
    "KALPITIYA": "kalpitiya",
    "KANDALAMA": "sigiriya",       # Kandalama is the proxy for Sigiriya/Dambulla
    "MINNERIYA TANK": "minneriya",
    "NEGOMBO": "negombo",
    "PASSIKUDA": "pasikudah",
    "THIRUKKOVIL": "arugambay",    # Closest station to Arugambay
    "YALA": "yala_national_park",
    "PANAWALA WOODEND": "kitulgala"
}

# 2. Regional Fallbacks (For KG locations with NO direct station data)
# We map them to the nearest available Station ID from above.
FALLBACK_MAPPING = {
    "ella": "nuwara_eliya",
    "horton_plains": "nuwara_eliya",
    "adams_peak": "nuwara_eliya",
    "wilpattu_national_park": "puttalam",
    "sinharaja": "ratnapura",
    "matara": "galle",
    "weligama": "galle",
    "unawatuna": "galle",
    "hikkaduwa": "galle",
    "beruwela": "bentota",
    "dambulla": "sigiriya",
    "knuckles_range": "kandy",
    "bundala_national_park": "hambantota",
    "nilaveli": "trincomalee",
    "kalkudah": "pasikudah",
    "adam's_peak": "nuwara_eliya"
}

# 3. Temperature Proxies
# Some stations have Rain but no Temp. We assign a nearby parent for Temp.
TEMP_PROXY_MAP = {
    "bentota": "galle",
    "kalpitiya": "puttalam",
    "sigiriya": "anuradhapura",   # Dry zone match
    "minneriya": "polonnaruwa",
    "negombo": "katunayake",
    "pasikudah": "batticaloa",
    "arugambay": "batticaloa",
    "yala_national_park": "hambantota",
    "kitulgala": "ratnapura"
}

def clean_column_names(df):
    """Strip whitespace from column names (fixes 'Jan ' issue)"""
    df.columns = df.columns.str.strip()
    return df

def process_wide_format(df, value_name, col_map=None):
    """Convert Wide (Jan..Dec columns) to Long format"""
    # Fix column names first
    df = clean_column_names(df)
    
    # Melt
    id_vars = [c for c in df.columns if c not in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']]
    df_long = df.melt(id_vars=id_vars, var_name='month_name', value_name=value_name)
    
    # Map Month Names to Numbers
    month_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 
                 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
    df_long['month'] = df_long['month_name'].map(month_map)
    
    # Create Date (Assume Day=1 for monthly aggregations)
    # Ensure yyyy is int
    df_long = df_long.dropna(subset=['yyyy', 'month'])
    df_long['yyyy'] = df_long['yyyy'].astype(int)
    df_long['date'] = pd.to_datetime(dict(year=df_long.yyyy, month=df_long.month, day=1))
    
    return df_long

def load_real_history():
    print("=== Loading Real Historical Data (2021-2025) ===")
    
    # 1. Define SIMPLE file paths
    rf_main_path = WEATHER_RAW_DIR / "rainfall_main.csv"
    rf_other_path = WEATHER_RAW_DIR / "rainfall_other.csv"
    tem_path = WEATHER_RAW_DIR / "temperature.csv"
    
    # --- DEBUG: CHECK FILES EXIST ---
    # This block prints what files Python ACTUALLY sees if your file is missing
    required_files = [rf_main_path, rf_other_path, tem_path]
    missing_flag = False
    for p in required_files:
        if not p.exists():
            print(f"❌ ERROR: Missing file -> {p.name}")
            missing_flag = True
    
    if missing_flag:
        print(f"\n📂 Contents of {WEATHER_RAW_DIR}:")
        # List all files in the directory to help you debug
        found_files = list(WEATHER_RAW_DIR.glob("*"))
        if not found_files:
            print("   (The folder is empty!)")
        else:
            for f in found_files:
                print(f"   - {f.name}")
        print("\n⚠️ Please rename your files in 'data_raw/weather' to match the required names above.")
        return # Stop execution here

    # --- 2. PROCESS MAIN RAINFALL ---
    print("   -> Processing Main Rainfall...")
    rf_main = pd.read_csv(rf_main_path)
    rf_main = process_wide_format(rf_main, 'rainfall')
    rf_main['station_clean'] = rf_main['station_name'].str.strip()
    rf_main = rf_main[['date', 'station_clean', 'rainfall']]

    # --- 3. PROCESS OTHER RAINFALL ---
    print("   -> Processing Other Rainfall...")
    rf_other = pd.read_csv(rf_other_path)
    # Rename cols to match
    rf_other['date'] = pd.to_datetime(dict(year=rf_other.Year, month=rf_other.Month, day=1))
    rf_other['rainfall'] = rf_other['Total(mm)']
    rf_other['station_clean'] = rf_other['station'].str.strip()
    rf_other = rf_other[['date', 'station_clean', 'rainfall']]
    
    # Combine Rainfall
    all_rain = pd.concat([rf_main, rf_other], ignore_index=True)
    
    # --- 4. PROCESS TEMPERATURE ---
    print("   -> Processing Temperature...")
    tem_df = pd.read_csv(tem_path)
    tem_df = process_wide_format(tem_df, 'temp_val')
    
    # Pivot to get MAX and MIN in same row
    tem_pivot = tem_df.pivot_table(
        index=['date', 'station_name'], 
        columns='abbreviation', 
        values='temp_val', 
        aggfunc='first'
    ).reset_index()
    
    # Calculate Average Temp
    if 'TMPMIN' in tem_pivot.columns and 'TMPMAX' in tem_pivot.columns:
        tem_pivot['avg_temp'] = (tem_pivot['TMPMAX'] + tem_pivot['TMPMIN']) / 2
    elif 'TMPMAX' in tem_pivot.columns:
        tem_pivot['avg_temp'] = tem_pivot['TMPMAX'] 
    else:
        tem_pivot['avg_temp'] = 28.0 
        
    tem_pivot['station_clean'] = tem_pivot['station_name'].str.strip()
    all_temp = tem_pivot[['date', 'station_clean', 'avg_temp']]

    # --- 5. MERGE & MAP ---
    print("   -> Merging and Mapping Locations...")
    merged = pd.merge(all_rain, all_temp, on=['date', 'station_clean'], how='left')
    merged['location_id'] = merged['station_clean'].map(STATION_TO_KG_ID)
    merged = merged.dropna(subset=['location_id'])
    
    # --- 6. IMPUTE MISSING TEMPERATURES ---
    def fill_missing_temp(row):
        if pd.notnull(row['avg_temp']):
            return row['avg_temp']
        
        loc_id = row['location_id']
        if loc_id in TEMP_PROXY_MAP:
            proxy_parent_id = TEMP_PROXY_MAP[loc_id]
            parent_val = merged.loc[
                (merged['location_id'] == proxy_parent_id) & 
                (merged['date'] == row['date']), 
                'avg_temp'
            ]
            if not parent_val.empty:
                return parent_val.values[0]
        return 28.0 

    merged['avg_temp'] = merged.apply(fill_missing_temp, axis=1)
    
    # --- 7. GENERATE FALLBACK LOCATIONS ---
    print("   -> Generating Regional Fallbacks...")
    fallback_rows = []
    for target_loc, source_loc in FALLBACK_MAPPING.items():
        source_data = merged[merged['location_id'] == source_loc].copy()
        if not source_data.empty:
            source_data['location_id'] = target_loc
            fallback_rows.append(source_data)
        
    if fallback_rows:
        fallback_df = pd.concat(fallback_rows)
        merged = pd.concat([merged, fallback_df], ignore_index=True)

    # --- 8. FINALIZE ---
    merged['weather_main'] = merged['rainfall'].apply(lambda x: 'Rain' if x > 50 else 'Clouds')
    merged['risk_level'] = merged['weather_main'].apply(lambda x: 'High' if x == 'Rain' else 'Low')
    
    final_df = merged[['date', 'location_id', 'avg_temp', 'rainfall', 'weather_main', 'risk_level']]
    final_df = final_df.sort_values(['location_id', 'date'])
    
    output_path = HISTORY_DIR / "cleaned_history.csv"
    final_df.to_csv(output_path, index=False)
    
    print(f"✅ Successfully processed {len(final_df)} records.")
    print(f"✅ Saved to: {output_path}")
    
if __name__ == "__main__":
    load_real_history()