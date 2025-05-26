import ee
import pandas as pd
import os # For accessing environment variables
from dotenv import load_dotenv # For loading .env file

# --- Load Environment Variables ---
# Construct the path to the .env file, assuming it's in the parent directory
# of the script's current directory.
script_dir = os.path.dirname(os.path.abspath(__file__)) # Gets the directory of the current script
project_root = os.path.dirname(script_dir) # Assumes script is in a subfolder
dotenv_path = os.path.join(project_root, '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    print(f"Loaded .env file from: {dotenv_path}")
else:
    print(f"Warning: .env file not found at {dotenv_path}. GCP_PROJECT_ID might not be set if not available globally.")

GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')

# Trigger the authentication flow.
try:
    if GCP_PROJECT_ID:
        print(f"Initializing Earth Engine with GCP Project ID: {GCP_PROJECT_ID}")
        # Credentials will be auto-discovered if you've run `earthengine authenticate`
        # and potentially `gcloud auth application-default login`
        ee.Initialize(project=GCP_PROJECT_ID)
    else:
        print("GCP_PROJECT_ID not found in environment. Attempting default initialization.")
        ee.Initialize() # Default initialization
except Exception as e:
    print(f"Error initializing Earth Engine: {e}")
    if not GCP_PROJECT_ID:
        print("Consider setting GCP_PROJECT_ID in your .env file or system environment.")
    print("Please ensure you have authenticated via `earthengine authenticate` in your terminal.")
    exit()

print("Earth Engine initialized successfully.")

# --- Load Legend Data ---
legend_csv_path = 'mapbiomas_c9_legend.csv' # Make sure this file exists
try:
    df_legend = pd.read_csv(legend_csv_path)
    print(f"Successfully loaded legend from: {legend_csv_path}")
except FileNotFoundError:
    print(f"ERROR: Legend file not found at {legend_csv_path}")
    print("Please create the legend CSV file and place it in the correct directory.")
    exit()
except Exception as e:
    print(f"Error loading legend CSV: {e}")
    exit()

# 1. Define Area of Interest (AOI)
# original coordinates:
# coords_sw_ne = [-12.85, -62.95, -12.70, -62.80] # lat_sw, lon_sw, lat_ne, lon_ne

# zoom in coordinates:
coords_sw_ne = [-12.88993, -62.96722, -12.71007, -62.78278]

aoi = ee.Geometry.Rectangle(coords_sw_ne[1], coords_sw_ne[0], coords_sw_ne[3], coords_sw_ne[2]) # lon_min, lat_min, lon_max, lat_max

# 2. Load the MapBiomas Image Collection 9 (LULC integration)
mapbiomas_lulc_asset_id = 'projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1'
lulc_image = ee.Image(mapbiomas_lulc_asset_id)
print(f"Loaded MapBiomas LULC Image: {mapbiomas_lulc_asset_id}")

# 3. Get band names (which represent years for this asset)
band_names = lulc_image.bandNames().getInfo()
classification_bands = sorted([b for b in band_names if b.startswith('classification_')])
print(f"Filtered classification bands: {classification_bands}")

# --- Configuration for area calculation ---
pixel_area_m2 = 30 * 30
m2_to_hectares = 0.0001
m2_to_km2 = 0.000001

# --- Store results ---
all_stats = []

# 4. Iterate through each year/band and calculate statistics
for band_name in classification_bands:
    year_str = band_name.split('_')[-1]
    print(f"\nProcessing year: {year_str} (Band: {band_name})")
    yearly_classification = lulc_image.select([band_name])
    stats = yearly_classification.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(), # Correct: instantiate the reducer
        geometry=aoi,
        scale=30,
        maxPixels=1e10
    )
    try:
        class_counts = stats.get(band_name).getInfo()
        if class_counts:
            print(f"  Raw counts for {year_str}: {class_counts}")
            for class_id_str, count in class_counts.items():
                all_stats.append({
                    'year': year_str,
                    'Code_ID': int(class_id_str), # Ensure Code_ID is integer for merging
                    'pixel_count': int(count),
                    'area_m2': int(count) * pixel_area_m2,
                    'area_hectares': int(count) * pixel_area_m2 * m2_to_hectares,
                    'area_km2': int(count) * pixel_area_m2 * m2_to_km2
                })
        else:
            print(f"  No data returned for {year_str} in the AOI.")
    except Exception as e:
        print(f"  Error processing or retrieving data for year {year_str}: {e}")
        all_stats.append({
            'year': year_str, 'Code_ID': -1, 'pixel_count': 0,
            'area_m2': 0, 'area_hectares': 0, 'area_km2': 0, 'error': str(e)
        })

# 5. Convert results to a Pandas DataFrame
df_raw_stats = pd.DataFrame(all_stats)

# 6. Merge with Legend Data
if not df_raw_stats.empty and not df_legend.empty:
    # Ensure the merge key 'Code_ID' is of the same type in both DataFrames
    df_raw_stats['Code_ID'] = df_raw_stats['Code_ID'].astype(int)
    df_legend['Code_ID'] = df_legend['Code_ID'].astype(int)
    
    df_stats_with_legend = pd.merge(df_raw_stats, df_legend, on='Code_ID', how='left')
    print("\n--- Summary Statistics DataFrame with Legend ---")
    print(df_stats_with_legend.head())
    
    output_csv_path = 'mapbiomas_area4_landcover_stats_collection9_with_legend.csv'
    df_stats_with_legend.to_csv(output_csv_path, index=False)
    print(f"\nStatistics with legend saved to: {output_csv_path}")

    print("\n--- Sanity Check: Total Area Calculated per Year (km2) ---")
    total_area_per_year = df_stats_with_legend.groupby('year')['area_km2'].sum()
    print(total_area_per_year)

    # Example: Show total area by major land cover class (Level1_EN) for the most recent year
    if not df_stats_with_legend.empty and classification_bands:
        most_recent_year = classification_bands[-1].split('_')[-1]
        print(f"\n--- Land Cover Summary for {most_recent_year} (km2) ---")
        summary_recent_year = df_stats_with_legend[df_stats_with_legend['year'] == most_recent_year]
        summary_by_level1 = summary_recent_year.groupby('Level1_EN')['area_km2'].sum().sort_values(ascending=False)
        print(summary_by_level1)

elif df_raw_stats.empty:
    print("No raw statistics were generated from GEE.")
else:
    print("Raw statistics generated, but legend is empty. Cannot merge.")