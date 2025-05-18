

import ee
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from pysheds.grid import Grid
from scipy.ndimage import generic_filter, distance_transform_edt
import matplotlib.pyplot as plt
import os
import time # To handle potential GEE export delays
from dotenv import load_dotenv # Import the library

# --- 0. Load Environment Variables and Initialize Earth Engine ---
load_dotenv()  # Load variables from .env file into environment variables

# Get the Project ID from the environment variable
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')

if not GCP_PROJECT_ID:
    print("Error: GCP_PROJECT_ID not found in .env file or environment variables.")
    print("Please create a .env file with GCP_PROJECT_ID='your-project-id'")
    exit()

try:
    # Pass the project ID to Initialize()
    ee.Initialize(project=GCP_PROJECT_ID)
except ee.EEException as e: # Catch specific EE exceptions
    if 'Please specify a project' in str(e) or 'no project found' in str(e):
        print(f"Initialization with project ID '{GCP_PROJECT_ID}' failed: {e}")
        print("This might be due to an incorrect project ID or insufficient permissions.")
        print("Attempting authentication (this might open a browser window)...")
        try:
            ee.Authenticate() # This will guide you through web authentication
            # After authentication, try initializing again with the project ID
            ee.Initialize(project=GCP_PROJECT_ID)
        except Exception as auth_e:
            print(f"Authentication or subsequent initialization failed: {auth_e}")
            print("Please ensure your .env file has the correct GCP_PROJECT_ID and you have authenticated successfully.")
            exit()
    else: # Other EEException
        print(f"An Earth Engine exception occurred during initialization: {e}")
        exit()
except Exception as e: # Catch any other general exceptions during initialization
    print(f"A general exception occurred during Earth Engine initialization: {e}")
    exit()


print(f"Google Earth Engine initialized with project: {GCP_PROJECT_ID}")

# --- 1. Define AOI and File Paths ---
output_dir = 'output_data_gee/' # Create this directory
os.makedirs(output_dir, exist_ok=True)

# Define your broader AOI (e.g., around São Francisco do Guaporé / Seringueiras)
# GEE uses [lon, lat] order for coordinates
# These are illustrative coordinates for a broader region
aoi_coordinates_gee = [
    [-63.8, -13.0],  # Bottom-left (lon, lat)
    [-62.8, -13.0],  # Bottom-right
    [-62.8, -12.0],  # Top-right
    [-63.8, -12.0],  # Top-left
    [-63.8, -13.0]   # Close polygon
]
aoi_geometry_gee = ee.Geometry.Polygon(aoi_coordinates_gee)

gee_dem_path = os.path.join(output_dir, 'gee_srtm_aoi.tif') # Path to save downloaded DEM

# --- 2. Acquire DEM from Google Earth Engine ---
print("Acquiring SRTM DEM from Google Earth Engine...")
# SRTM 1 Arc-Second Global, Version 3
srtm = ee.Image('USGS/SRTMGL1_003')

# Clip the SRTM image to your AOI
srtm_aoi = srtm.clip(aoi_geometry_gee)

# Get information about the projection of the SRTM image to use for export
# We'll export in its native projection to start
projection_info = srtm.projection().getInfo()
crs_gee = projection_info['crs']
transform_gee = projection_info['transform'] # This is affine transform [scaleX, shearX, translateX, shearY, scaleY, translateY]

print(f"GEE SRTM native CRS: {crs_gee}")
print(f"GEE SRTM native transform: {transform_gee}")

# Export the clipped DEM to Google Drive (or directly download if small enough)
# For larger areas, exporting to Drive is more robust.
# We'll attempt direct download here using getDownloadURL for simplicity,
# but this might time out or fail for very large AOIs.
task_config = {
    'image': srtm_aoi.select('elevation'), # Select the elevation band
    'description': 'SRTM_AOI_Export',
    'scale': 30, # Approximate scale of SRTM 1-arcsec in meters
    'region': aoi_geometry_gee,
    'fileFormat': 'GeoTIFF',
    # 'crs': crs_gee, # Export in native projection
    # 'crsTransform': transform_gee # Using scale is often simpler
}

# --- Option A: Direct Download (may fail for large AOIs or return ZIP) ---
download_success = False
actual_dem_path_for_pysheds = gee_dem_path # Assume it's the direct path initially

try:
    print("Attempting direct download from GEE...")
    if not isinstance(srtm_aoi, ee.Image):
        print("Error: srtm_aoi is not an ee.Image object.")
        raise Exception("Invalid GEE Image object for download")
    
    image_to_download = srtm_aoi.select('elevation')

    download_url = image_to_download.getDownloadURL({
        'scale': 30,
        'region': aoi_geometry_gee,
        'format': 'GEO_TIFF' # Request GeoTIFF
    })
    
    print(f"Generated download URL: {download_url[:100]}...")

    import requests
    import shutil
    import zipfile # For handling ZIP files

    with requests.Session() as session:
        response = session.get(download_url, stream=True, timeout=300)
    
    print(f"Download response status code: {response.status_code}")
    content_type = response.headers.get('Content-Type', '').lower()
    print(f"Download response content-type: {content_type}")

    if response.status_code == 200:
        temp_download_path = gee_dem_path + ".download" # Download to a temp name
        with open(temp_download_path, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        print(f"SRTM DEM for AOI potentially downloaded to {temp_download_path}")

        # Check if it's a ZIP file
        if 'zip' in content_type or zipfile.is_zipfile(temp_download_path):
            print("Downloaded file is a ZIP archive. Extracting...")
            with zipfile.ZipFile(temp_download_path, 'r') as zip_ref:
                # Find the .tif file within the zip
                tif_files_in_zip = [name for name in zip_ref.namelist() if name.lower().endswith('.tif')]
                if tif_files_in_zip:
                    extracted_tif_name = tif_files_in_zip[0] # Assume the first .tif is the one we want
                    zip_ref.extract(extracted_tif_name, path=output_dir)
                    # Rename the extracted file to our expected gee_dem_path
                    # or ensure actual_dem_path_for_pysheds points to it
                    extracted_file_full_path = os.path.join(output_dir, extracted_tif_name)
                    if os.path.exists(gee_dem_path) and gee_dem_path != extracted_file_full_path:
                         os.remove(gee_dem_path) # Remove if it was a placeholder or previous bad download
                    if gee_dem_path != extracted_file_full_path:
                        os.rename(extracted_file_full_path, gee_dem_path)

                    actual_dem_path_for_pysheds = gee_dem_path
                    print(f"Extracted '{extracted_tif_name}' to '{actual_dem_path_for_pysheds}'")
                else:
                    print("Error: ZIP file downloaded, but no .tif file found inside.")
                    download_success = False
            os.remove(temp_download_path) # Clean up the zip file
        else:
            # Not a zip, assume it's the direct GeoTIFF, rename it
            if os.path.exists(gee_dem_path) and gee_dem_path != temp_download_path:
                 os.remove(gee_dem_path)
            os.rename(temp_download_path, gee_dem_path)
            actual_dem_path_for_pysheds = gee_dem_path
        
        # Verify the final DEM file (either extracted or directly downloaded)
        if os.path.exists(actual_dem_path_for_pysheds):
            try:
                with rasterio.open(actual_dem_path_for_pysheds) as test_ds:
                    print(f"Successfully opened final GeoTIFF: {test_ds.count} band(s), {test_ds.width}x{test_ds.height} pixels.")
                download_success = True
            except rasterio.errors.RasterioIOError:
                print(f"Error: Final file {actual_dem_path_for_pysheds} is not a valid GeoTIFF.")
                if os.path.exists(actual_dem_path_for_pysheds): os.remove(actual_dem_path_for_pysheds)
                download_success = False
        else:
            print(f"Error: Expected DEM file {actual_dem_path_for_pysheds} not found after download/extraction attempt.")
            download_success = False
            
    else: # response.status_code != 200
        print(f"Failed to download directly. Status code: {response.status_code}")
        try:
            print(f"Error response from GEE: {response.content.decode('utf-8', errors='ignore')[:500]}")
        except: pass
        download_success = False

    if not download_success:
        print("Consider exporting to Google Drive for larger or problematic AOIs (Option B).")
        raise Exception("Direct download failed or produced an invalid file.")

except Exception as e_direct_download:
    # ... (rest of the Google Drive export fallback logic as before) ...
    print(f"Direct download from GEE failed or not chosen: {e_direct_download}")
    print("If the error was 'Image.clip: Output of image computation is too large' or similar, your AOI is too big for direct download.")
    print("Proceeding with Google Drive export option (ensure relevant code block is uncommented)...")
    # --- Option B: Export to Google Drive (more robust for larger areas) ---
    # Ensure the task_config is correctly defined if using this block
    task_config_drive = {
        'image': srtm_aoi.select('elevation'),
        'description': 'SRTM_AOI_Export_Drive',
        'scale': 30,
        'region': aoi_geometry_gee,
        'fileFormat': 'GeoTIFF',
        'folder': 'GEE_Exports',
        'fileNamePrefix': 'srtm_aoi_rondonia'
    }
    task = ee.batch.Export.image.toDrive(**task_config_drive)
    task.start()
    print(f"Exporting SRTM DEM for AOI to Google Drive. Task ID: {task.id}")
    print("Please monitor the 'Tasks' tab in the GEE Code Editor or use 'task.status()' to check progress.")
    print(f"Once complete, download '{task_config_drive['fileNamePrefix']}.tif' from your 'GEE_Exports' Drive folder, ensure it's named '{os.path.basename(gee_dem_path)}' in '{os.path.dirname(gee_dem_path)}', and re-run the script from step 3 (after commenting out the GEE download/export sections).")
    exit()


# --- Check if DEM was downloaded and processed successfully ---
if not download_success or not os.path.exists(actual_dem_path_for_pysheds):
    print(f"Error: DEM file {actual_dem_path_for_pysheds} not found or invalid. Please ensure it was downloaded and extracted correctly.")
    exit()

# --- 3. Hydrological Analysis with PySheds ---
print(f"Starting hydrological analysis with PySheds using: {actual_dem_path_for_pysheds}")
grid = Grid.from_raster(actual_dem_path_for_pysheds, data_name='dem')
# Now grid.dem should be the Raster object for your initial DEM

# Fill depressions
print("Filling depressions...")
# Pass the Raster object grid.dem to the 'dem' parameter
grid.fill_depressions(dem=grid.dem, out_name='flooded_dem')
# Now grid.flooded_dem is the Raster object for the filled DEM

# Calculate flow direction
print("Calculating flow direction...")
# Pass the Raster object grid.flooded_dem to the 'dem' parameter
grid.flowdir(dem=grid.flooded_dem, out_name='fdir')
# Now grid.fdir is the Raster object for flow direction

# Calculate flow accumulation
print("Calculating flow accumulation...")
# For accumulation, using the string name with 'data' often works,
# as it might do the lookup internally. If this fails, try data=grid.fdir
grid.accumulation(data='fdir', out_name='acc')
# Now grid.acc is the Raster object for flow accumulation

# Extract stream network
stream_threshold = 1000
print(f"Extracting stream network with threshold: {stream_threshold}...")
# Pass the Raster objects grid.fdir and grid.acc
grid.extract_river_network(fdir=grid.fdir, acc=grid.acc, threshold=stream_threshold, out_name='streams')
# Now grid.streams is the Raster object for the stream network

streams_raster = grid.streams.astype(np.uint8)

# Save the streams raster
streams_path = os.path.join(output_dir, 'streams_gee.tif')
with rasterio.open(actual_dem_path_for_pysheds) as src_meta_provider:
    profile = src_meta_provider.profile.copy()
    profile.update(dtype=rasterio.uint8, count=1, compress='lzw')
    with rasterio.open(streams_path, 'w', **profile) as dst:
        dst.write(streams_raster, 1)
print(f"Streams raster saved to {streams_path}")

# --- 4. Identify Interfluve Zones (remains largely the same) ---

# Method 1: Distance from Streams
print("Calculating distance from streams...")
binary_streams = (streams_raster > 0).astype(np.uint8)
distance_to_streams = distance_transform_edt(1 - binary_streams)
distance_interfluve_threshold_pixels = 15  # EXAMPLE
interfluves_by_distance = (distance_to_streams > distance_interfluve_threshold_pixels).astype(np.uint8)

interfluves_dist_path = os.path.join(output_dir, 'interfluves_by_distance_gee.tif')
with rasterio.open(streams_path) as src_meta_provider:
    profile = src_meta_provider.profile.copy()
    with rasterio.open(interfluves_dist_path, 'w', **profile) as dst:
        dst.write(interfluves_by_distance, 1)
print(f"Interfluves by distance saved to {interfluves_dist_path}")


# Method 2: Topographic Position Index (TPI)
print("Calculating TPI...")
with rasterio.open(gee_dem_path) as src:
    dem_array = src.read(1).astype(np.float32) # Ensure float for calculations
    profile = src.profile.copy()

kernel_size = 9  # EXAMPLE
pad_width = kernel_size // 2
# Handle NaN values in DEM if any before padding/filtering, e.g., by interpolating or setting to a value
dem_array_no_nan = np.nan_to_num(dem_array, nan=np.nanmean(dem_array)) # Example: replace NaN with mean

dem_padded = np.pad(dem_array_no_nan, pad_width, mode='reflect')

def mean_filter_nan_aware(arr): # TPI calculation needs to be robust to NaNs if present
    valid_arr = arr[~np.isnan(arr)]
    if valid_arr.size == 0:
        return np.nan
    return np.mean(valid_arr)

mean_elevation_neighborhood = generic_filter(
    dem_padded,
    mean_filter_nan_aware, # Use NaN-aware mean
    size=kernel_size,
    mode='constant',
    cval=np.nan
)
mean_elevation_neighborhood = mean_elevation_neighborhood[pad_width:-pad_width, pad_width:-pad_width]

tpi = dem_array - mean_elevation_neighborhood # Original dem_array might have NaNs, so TPI will too

tpi_interfluve_threshold = 0.5  # EXAMPLE
# Handle NaNs in TPI before comparison
interfluves_by_tpi = np.where(np.isnan(tpi), 0, (tpi > tpi_interfluve_threshold)).astype(np.uint8)


tpi_path = os.path.join(output_dir, 'tpi_gee.tif')
interfluves_tpi_path = os.path.join(output_dir, 'interfluves_by_tpi_gee.tif')
tpi_profile = profile.copy()
tpi_profile.update(dtype=rasterio.float32, compress='lzw')
with rasterio.open(tpi_path, 'w', **tpi_profile) as dst:
    dst.write(tpi.astype(rasterio.float32), 1) # Save TPI with potential NaNs

interfluve_tpi_profile = profile.copy()
interfluve_tpi_profile.update(dtype=rasterio.uint8, compress='lzw')
with rasterio.open(interfluves_tpi_path, 'w', **interfluve_tpi_profile) as dst:
    dst.write(interfluves_by_tpi, 1)
print(f"TPI saved to {tpi_path}")
print(f"Interfluves by TPI saved to {interfluves_tpi_path}")


# Method 3: Combine Distance and TPI
print("Combining distance and TPI methods for interfluves...")
if interfluves_by_distance.shape == interfluves_by_tpi.shape:
    combined_interfluves = (interfluves_by_distance & interfluves_by_tpi).astype(np.uint8)
    combined_interfluves_path = os.path.join(output_dir, 'combined_interfluves_gee.tif')
    with rasterio.open(streams_path) as src_meta_provider:
        profile = src_meta_provider.profile.copy()
        with rasterio.open(combined_interfluves_path, 'w', **profile) as dst:
            dst.write(combined_interfluves, 1)
    print(f"Combined interfluves saved to {combined_interfluves_path}")
else:
    print("Shapes of distance and TPI interfluve arrays do not match. Skipping combination.")

print("Processing complete. Check the output_data_gee directory.")

