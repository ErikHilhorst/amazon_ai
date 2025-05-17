import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from scipy.ndimage import generic_filter, distance_transform_edt
import os
import logging
import whitebox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

try:
    wbt = whitebox.WhiteboxTools()
    wbt.verbose = True # Keep True for now
    logger.info(f"WhiteboxTools initialized. Version: {wbt.version()}")
except Exception as e:
    logger.error(f"Failed to initialize WhiteboxTools: {e}", exc_info=True)
    exit()

project_base_dir = os.path.dirname(os.path.abspath(__file__))
logger.info(f"Project base directory determined as: {project_base_dir}")

output_wbt_subdir = 'output_data_gee_wbt'
output_dir_wbt_abs = os.path.join(project_base_dir, output_wbt_subdir)
os.makedirs(output_dir_wbt_abs, exist_ok=True)
logger.info(f"Absolute output directory for WBT: {output_dir_wbt_abs}")

input_dem_subdir = 'output_data_gee'
input_dem_filename = 'gee_srtm_aoi.tif'
actual_dem_path_abs = os.path.join(project_base_dir, input_dem_subdir, input_dem_filename)

if not os.path.exists(actual_dem_path_abs):
    logger.critical(f"CRITICAL: Input DEM file not found at {actual_dem_path_abs}.")
    try:
        logger.info("Attempting to create a dummy DEM as placeholder...")
        profile_dummy = {
            'driver': 'GTiff', 'dtype': rasterio.int16, 'nodata': -32768,
            'width': 100, 'height': 100, 'count': 1,
            'crs': rasterio.crs.CRS.from_epsg(4326),
            'transform': rasterio.transform.from_origin(0, 0, 1, 1), 'compress': 'lzw'
        }
        dem_data_dummy = np.arange(10000, dtype=np.int16).reshape(100, 100) + 100
        dem_data_dummy[0:10, 0:10] = -32768
        os.makedirs(os.path.dirname(actual_dem_path_abs), exist_ok=True)
        with rasterio.open(actual_dem_path_abs, 'w', **profile_dummy) as dst:
            dst.write(dem_data_dummy, 1)
        logger.info(f"Dummy DEM created at {actual_dem_path_abs}. PLEASE REPLACE WITH YOUR ACTUAL DEM.")
    except Exception as e:
        logger.error(f"Could not create dummy DEM. Error: {e}", exc_info=True)
        exit()
else:
    logger.info(f"Using existing DEM: {actual_dem_path_abs}")

# --- Define ABSOLUTE paths for intermediate and final WhiteboxTools files ---
wbt_compatible_dem_filename = 'gee_srtm_aoi_wbt_compat.tif'
wbt_compatible_dem_path_abs = os.path.join(output_dir_wbt_abs, wbt_compatible_dem_filename) # Store compatible DEM in WBT output dir

filled_dem_path_abs = os.path.join(output_dir_wbt_abs, 'filled_dem_wbt.tif')
d8_pointer_path_abs = os.path.join(output_dir_wbt_abs, 'd8_pointer_wbt.tif')
facc_path_abs = os.path.join(output_dir_wbt_abs, 'facc_wbt.tif')
streams_wbt_path_abs = os.path.join(output_dir_wbt_abs, 'streams_raw_wbt.tif')
final_streams_path_abs = os.path.join(output_dir_wbt_abs, 'streams_gee_wbt_final.tif')
interfluves_dist_path_abs = os.path.join(output_dir_wbt_abs, 'interfluves_by_distance_gee_wbt.tif')
tpi_path_abs = os.path.join(output_dir_wbt_abs, 'tpi_gee_wbt.tif')
interfluves_tpi_path_abs = os.path.join(output_dir_wbt_abs, 'interfluves_by_tpi_gee_wbt.tif')
combined_interfluves_path_abs = os.path.join(output_dir_wbt_abs, 'combined_interfluves_gee_wbt.tif')

initial_profile = None
initial_nodata_value = None
dem_width = None
dem_height = None
dem_crs = None # Store CRS for TPI output profile
dem_transform = None # Store transform for TPI output profile

try:
    with rasterio.open(actual_dem_path_abs) as src:
        initial_profile = src.profile # Keep original profile for reference and final outputs
        initial_nodata_value = src.nodatavals[0] if src.nodatavals else None
        dem_width = src.width
        dem_height = src.height
        dem_crs = src.crs
        dem_transform = src.transform
        logger.info(f"Initial DEM properties: dtype={src.dtypes[0]}, nodata={initial_nodata_value}, W={dem_width}, H={dem_height}")
except Exception as e:
    logger.error(f"Failed to read initial DEM properties from {actual_dem_path_abs}: {e}", exc_info=True)
    exit()

# --- Pre-process input DEM for WhiteboxTools compatibility ---
logger.info(f"Preparing WBT-compatible DEM from {actual_dem_path_abs} to {wbt_compatible_dem_path_abs}")
dem_input_for_wbt = "" # Initialize
try:
    with rasterio.open(actual_dem_path_abs) as src:
        data = src.read(1)
        profile_for_wbt_dem = src.profile.copy()
        
        # Set LZW compression for WBT compatibility
        profile_for_wbt_dem['compress'] = 'lzw'
        
        # Ensure other essential tags are consistent
        profile_for_wbt_dem.update({
            'driver': 'GTiff',
            'dtype': src.dtypes[0],
            'nodata': initial_nodata_value,
            'width': dem_width,
            'height': dem_height,
            'count': 1,
            'crs': dem_crs,
            'transform': dem_transform
        })
        # Remove potentially problematic tags if they exist from original profile
        profile_for_wbt_dem.pop('photometric', None) 
        profile_for_wbt_dem.pop('predictor', None) # Predictor might interact with LZW in ways WBT doesn't like for some data types

        with rasterio.open(wbt_compatible_dem_path_abs, 'w', **profile_for_wbt_dem) as dst:
            dst.write(data, 1)
    logger.info(f"WBT-compatible DEM saved to {wbt_compatible_dem_path_abs} with {profile_for_wbt_dem.get('compress', 'no')} compression.")
    dem_input_for_wbt = wbt_compatible_dem_path_abs
except Exception as e:
    logger.error(f"Failed to create WBT-compatible DEM: {e}", exc_info=True)
    exit()

# --- 1. Fill Depressions ---
logger.info(f"Filling depressions with WhiteboxTools using: {dem_input_for_wbt}")
try:
    wbt.fill_depressions(
        dem=dem_input_for_wbt,
        output=filled_dem_path_abs,
        fix_flats=True
    )
    logger.info(f"Depressions filled. Output: {filled_dem_path_abs}")
except Exception as e:
    logger.error(f"Error during WhiteboxTools FillDepressions: {e}", exc_info=True)
    exit()

# --- 2. Calculate D8 Flow Pointers ---
logger.info("Calculating D8 flow pointers with WhiteboxTools...")
try:
    wbt.d8_pointer(
        dem=filled_dem_path_abs,
        output=d8_pointer_path_abs
    )
    logger.info(f"D8 flow pointers calculated. Output: {d8_pointer_path_abs}")
except Exception as e:
    logger.error(f"Error during WhiteboxTools D8Pointer: {e}", exc_info=True)
    exit()

# --- 3. Calculate D8 Flow Accumulation ---
logger.info("Calculating D8 flow accumulation with WhiteboxTools...")
try:
    wbt.d8_flow_accumulation(
        i=d8_pointer_path_abs,
        output=facc_path_abs,
        out_type="cells"
    )
    logger.info(f"D8 flow accumulation calculated. Output: {facc_path_abs}")
except Exception as e:
    logger.error(f"Error during WhiteboxTools D8FlowAccumulation: {e}", exc_info=True)
    exit()

# --- 4. Extract Stream Network ---
logger.info("Extracting stream network with WhiteboxTools...")
stream_threshold = 3
try:
    wbt.extract_streams(
        facc_path_abs,
        streams_wbt_path_abs,
        threshold=stream_threshold,
        zero_background=True
    )
    logger.info(f"Stream network extracted. Raw output: {streams_wbt_path_abs}")
except Exception as e:
    logger.error(f"Error during WhiteboxTools ExtractStreams: {e}", exc_info=True)
    exit()

# --- 5. Load Streams into NumPy array and Save with consistent metadata ---
streams_numpy_array = None
# Use the initial_profile as a base for streams_profile, then update
streams_profile = initial_profile.copy() 
intended_streams_nodata_val = 0

if os.path.exists(streams_wbt_path_abs):
    try:
        with rasterio.open(streams_wbt_path_abs) as src:
            streams_numpy_array = src.read(1).astype(np.uint8)
            if streams_numpy_array.shape != (dem_height, dem_width):
                 logger.warning(f"Stream raster shape {streams_numpy_array.shape} differs from DEM ({dem_height}, {dem_width}). This might be an issue.")

            streams_profile.update({
                'dtype': rasterio.uint8,
                'nodata': intended_streams_nodata_val,
                'compress': 'lzw',
                'count': 1
            })
        logger.info(f"Streams raster loaded from {streams_wbt_path_abs} into NumPy array. Shape: {streams_numpy_array.shape}")
        
        with rasterio.open(final_streams_path_abs, 'w', **streams_profile) as dst:
            dst.write(streams_numpy_array, 1)
        logger.info(f"Processed streams raster saved to {final_streams_path_abs}")

    except Exception as e:
        logger.error(f"Failed to load or save processed streams raster from {streams_wbt_path_abs}: {e}", exc_info=True)
        exit()
else:
    logger.error(f"WhiteboxTools stream output not found: {streams_wbt_path_abs}")
    exit()

# --- Interfluve Analysis ---
if streams_numpy_array is not None:
    logger.info("Starting Interfluve Analysis...")
    logger.info("Calculating distance from streams...")
    distance_to_streams = distance_transform_edt(1 - streams_numpy_array)
    distance_interfluve_threshold_pixels = 15
    interfluves_by_distance = (distance_to_streams > distance_interfluve_threshold_pixels).astype(np.uint8)

    # Use streams_profile as base for uint8 outputs if suitable
    profile_uint8_nodata0 = streams_profile.copy() 

    with rasterio.open(interfluves_dist_path_abs, 'w', **profile_uint8_nodata0) as dst:
        dst.write(interfluves_by_distance, 1)
    logger.info(f"Interfluves by distance saved to {interfluves_dist_path_abs}")

    logger.info("Calculating TPI using the filled DEM...")
    dem_for_tpi_np = None
    if os.path.exists(filled_dem_path_abs):
        try:
            with rasterio.open(filled_dem_path_abs) as src:
                dem_for_tpi_np = src.read(1).astype(np.float32)
                tpi_input_dem_nodata = src.nodatavals[0] if src.nodatavals else None
                
                logger.info(f"Filled DEM for TPI loaded from {filled_dem_path_abs}. Original dtype: {src.dtypes[0]}, nodata: {tpi_input_dem_nodata}. Converted to float32.")
                if tpi_input_dem_nodata is not None:
                    dem_for_tpi_np[dem_for_tpi_np == tpi_input_dem_nodata] = np.nan
                
        except Exception as e:
            logger.error(f"Failed to load filled DEM for TPI from {filled_dem_path_abs}: {e}", exc_info=True)
            exit()
    else:
        logger.error(f"Filled DEM file not found: {filled_dem_path_abs}. Cannot calculate TPI.")
        exit()

    if dem_for_tpi_np is not None:
        kernel_size = 9
        pad_width = kernel_size // 2
        
        dem_mask_for_tpi = np.isnan(dem_for_tpi_np)
        
        dem_mean_for_nan_replacement = np.nanmean(dem_for_tpi_np[~dem_mask_for_tpi]) if not np.all(dem_mask_for_tpi) else 0
        dem_array_no_nodata = np.where(dem_mask_for_tpi, dem_mean_for_nan_replacement, dem_for_tpi_np)
        
        dem_padded = np.pad(dem_array_no_nodata, pad_width, mode='reflect')

        mean_elevation_neighborhood = generic_filter(
            dem_padded, np.mean, size=kernel_size, mode='reflect'
        )
        mean_elevation_neighborhood = mean_elevation_neighborhood[pad_width:-pad_width, pad_width:-pad_width]

        tpi = dem_for_tpi_np - mean_elevation_neighborhood
        
        tpi_interfluve_threshold = 0.5
        interfluves_by_tpi = np.where(np.isnan(tpi), 0, (tpi > tpi_interfluve_threshold)).astype(np.uint8)

        # Use initial_profile as base for TPI output, then update for float32/NaN nodata
        tpi_profile_out = initial_profile.copy() 
        tpi_profile_out.update(dtype=rasterio.float32, nodata=np.float32(np.nan), compress='lzw', count=1)
        with rasterio.open(tpi_path_abs, 'w', **tpi_profile_out) as dst:
            dst.write(tpi.astype(rasterio.float32), 1)
        logger.info(f"TPI raster saved to {tpi_path_abs}")

        with rasterio.open(interfluves_tpi_path_abs, 'w', **profile_uint8_nodata0) as dst:
            dst.write(interfluves_by_tpi, 1)
        logger.info(f"Interfluves by TPI saved to {interfluves_tpi_path_abs}")

        logger.info("Combining distance and TPI methods for interfluves...")
        if interfluves_by_distance.shape == interfluves_by_tpi.shape:
            combined_interfluves = (interfluves_by_distance & interfluves_by_tpi).astype(np.uint8)
            with rasterio.open(combined_interfluves_path_abs, 'w', **profile_uint8_nodata0) as dst:
                dst.write(combined_interfluves, 1)
            logger.info(f"Combined interfluves saved to {combined_interfluves_path_abs}")
        else:
            logger.warning(f"Shapes of distance ({interfluves_by_distance.shape}) and TPI ({interfluves_by_tpi.shape}) interfluve arrays do not match. Skipping combination.")
    else:
        logger.error("Could not prepare DEM for TPI. Skipping TPI-based interfluve analysis.")
else:
    logger.error("streams_numpy_array is None. Processing halted before interfluve analysis.")

logger.info(f"Processing complete. Check the {output_dir_wbt_abs} directory.")