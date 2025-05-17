import pysheds
from pysheds.grid import Grid
import numpy as np
import rasterio
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

output_dir = 'output_data_gee/'
os.makedirs(output_dir, exist_ok=True)
actual_dem_path_for_pysheds = os.path.join(output_dir, 'gee_srtm_aoi.tif')

if not os.path.exists(actual_dem_path_for_pysheds):
    logger.critical(f"CRITICAL: DEM file not found at {actual_dem_path_for_pysheds}")
    exit()

logger.info(f"Starting hydrological analysis with PySheds (sGrid - fdir consistency for acc) using: {actual_dem_path_for_pysheds}")

grid = Grid()
logger.debug(f"Initial grid.nodata: {grid.nodata} (type: {type(grid.nodata)}), grid.dtype: {getattr(grid, 'dtype', 'N/A')}")

logger.info(f"Loading DEM from {actual_dem_path_for_pysheds}...")
dem_raster_view = grid.read_raster(actual_dem_path_for_pysheds, data_name='dem_initial')
logger.info(f"DEM RasterView loaded. Type: {type(dem_raster_view)}")
logger.debug(f"dem_raster_view.dtype: {dem_raster_view.dtype}, dem_raster_view.nodata (direct): {getattr(dem_raster_view, 'nodata', 'N/A')}")

if hasattr(dem_raster_view, 'nodata') and dem_raster_view.nodata is not None:
    grid.nodata = dem_raster_view.nodata
    logger.debug(f"Set grid.nodata from dem_raster_view.nodata: {grid.nodata} (type: {type(grid.nodata)})")
else:
    if dem_raster_view.dtype == np.int16: # Default for SRTM if nodata was None
        grid.nodata = np.int16(-32768)
        logger.debug(f"dem_raster_view.nodata was problematic, set grid.nodata to default SRTM: {grid.nodata} (type: {type(grid.nodata)})")
    else: # Fallback to a dtype-appropriate zero or let PySheds handle
        grid.nodata = np.array(0, dtype=dem_raster_view.dtype).item() if dem_raster_view.dtype else 0
        logger.debug(f"dem_raster_view.nodata was problematic, set grid.nodata to typed zero: {grid.nodata} (type: {type(grid.nodata)})")


if hasattr(dem_raster_view, 'dtype'):
    grid.dtype = dem_raster_view.dtype
    logger.debug(f"Set grid.dtype from dem_raster_view.dtype: {grid.dtype}")

logger.info(f"Grid properties after read_raster & updates: Shape: {grid.shape}, Affine: {grid.affine}, Nodata: {grid.nodata}, CRS: {grid.crs}, Dtype: {grid.dtype}")

logger.info("Filling depressions...")
flooded_dem_raster_view = grid.fill_depressions(dem=dem_raster_view, out_name='flooded_dem')
logger.info(f"Depressions filled. Returned type: {type(flooded_dem_raster_view)}")
logger.debug(f"flooded_dem_raster_view.dtype: {flooded_dem_raster_view.dtype}, .nodata: {getattr(flooded_dem_raster_view, 'nodata', 'N/A')}")

logger.info("Calculating flow direction...")
fdir_raster_view = None
if flooded_dem_raster_view is not None:
    grid_nodata_backup_fdir = grid.nodata
    grid_dtype_backup_fdir = grid.dtype
    
    # PySheds sGrid seems to make fdir output int64. Let's align with that.
    # The nodata for fdir (0) should also be int64 to match fdir_raster_view.dtype.
    flowdir_output_nodata_typed = np.int64(0)
    # Temporarily set grid.dtype to match the *expected output dtype of fdir_raster_view* if known,
    # or a common type like int64 if sGrid is defaulting to it.
    # Let's assume sGrid will make fdir int64, so make grid context compatible.
    flowdir_internal_dtype = np.int64 # Based on previous log output for fdir_raster_view.dtype
    
    logger.debug(f"Temporarily setting grid.nodata to {flowdir_output_nodata_typed} (type {type(flowdir_output_nodata_typed)}) and grid.dtype to {flowdir_internal_dtype} for flowdir.")
    grid.nodata = flowdir_output_nodata_typed
    grid.dtype = flowdir_internal_dtype # Make grid context match expected fdir output
    try:
        # Pass nodata_out as the same type as grid.nodata (which is now int64(0))
        fdir_raster_view = grid.flowdir(dem=flooded_dem_raster_view, out_name='fdir', nodata_out=flowdir_output_nodata_typed)
        logger.info(f"Flow direction calculated. Returned type: {type(fdir_raster_view)}")
        logger.debug(f"fdir_raster_view.dtype: {fdir_raster_view.dtype}, .nodata: {getattr(fdir_raster_view, 'nodata', 'N/A')}")
        # We expect fdir_raster_view.dtype to be int64 and .nodata to be int64(0)
    except Exception as e:
        logger.error(f"Error during grid.flowdir: {e}", exc_info=True)
        raise
    finally:
        grid.nodata = grid_nodata_backup_fdir
        grid.dtype = grid_dtype_backup_fdir
        logger.debug(f"Restored grid.nodata to: {grid.nodata} (type: {type(grid.nodata)}), grid.dtype to: {grid.dtype}")
else:
    logger.warning("Skipping flow direction as flooded_dem_raster_view is None.")
    exit("Flow direction failed.")


logger.info("Calculating flow accumulation...")
acc_raster_view = None
if fdir_raster_view is not None:
    # No temporary changes to grid.nodata/dtype here, as accumulation's output sview.Raster
    # is created using fdir_raster_view.viewfinder.
    # We need fdir_raster_view.nodata and fdir_raster_view.dtype to be self-consistent
    # and for fdir_raster_view.nodata to be castable to accumulation's output dtype.
    logger.debug(f"grid.nodata before accumulation: {grid.nodata} (type: {type(grid.nodata)}), grid.dtype: {grid.dtype}")
    logger.debug(f"USING fdir_raster_view for accumulation input: dtype={fdir_raster_view.dtype}, nodata={getattr(fdir_raster_view, 'nodata', 'N/A')}")

    try:
        grid.accumulation(fdir=fdir_raster_view, out_name='acc')
        logger.info(f"Flow accumulation calculated.")
        acc_raster_view = grid.get_data('acc', return_sview=True)
        logger.info(f"Accessed 'acc' via grid.get_data(), type: {type(acc_raster_view)}")
        logger.debug(f"acc_raster_view.dtype: {acc_raster_view.dtype}, .nodata: {getattr(acc_raster_view, 'nodata', 'N/A')}")
    except Exception as e:
        logger.error(f"Error during/after grid.accumulation: {e}", exc_info=True)
        raise
else:
    logger.warning("Skipping flow accumulation as fdir_raster_view was not created or is None.")
    exit("Accumulation failed.")

# ... (Rest of the script for stream extraction and saving) ...
# Apply similar logic for temporary grid.nodata/dtype before extract_river_network if needed.
# Its output is uint8, nodata=0.
logger.info("Extracting stream network with threshold: 1000...")
streams_raster_view = None
if acc_raster_view is not None:
    grid_nodata_backup_streams = grid.nodata
    grid_dtype_backup_streams = grid.dtype
    streams_output_nodata_typed = np.uint8(0)
    streams_output_dtype = np.uint8

    logger.debug(f"Temporarily setting grid.nodata to {streams_output_nodata_typed} and grid.dtype to {streams_output_dtype} for streams.")
    grid.nodata = streams_output_nodata_typed
    grid.dtype = streams_output_dtype
    try:
        # extract_river_network uses fdir_raster_view and acc_raster_view.
        # Its output sview.Raster is created using the main grid's current viewfinder (nodata/dtype).
        grid.extract_river_network(fdir=fdir_raster_view, acc=acc_raster_view, threshold=1000, out_name='streams')
        logger.info(f"Stream network extracted.")
        streams_raster_view = grid.get_data('streams', return_sview=True)
        logger.info(f"Accessed 'streams' via grid.get_data(), type: {type(streams_raster_view)}")
        logger.debug(f"streams_raster_view.dtype: {streams_raster_view.dtype}, .nodata: {getattr(streams_raster_view, 'nodata', 'N/A')}")

        if streams_raster_view is not None:
            streams_path = os.path.join(output_dir, 'streams_gee.tif')
            profile = {
                'driver': 'GTiff', 'dtype': rasterio.uint8, 'nodata': streams_output_nodata_typed.item(),
                'width': grid.shape[1], 'height': grid.shape[0], 'count': 1,
                'crs': grid.crs, 'transform': grid.affine, 'compress': 'lzw'
            }
            if hasattr(streams_raster_view, 'filled'):
                data_to_save = streams_raster_view.filled(streams_output_nodata_typed.item()).astype(np.uint8)
            elif isinstance(streams_raster_view, np.ndarray):
                data_to_save = streams_raster_view.astype(np.uint8)
            else:
                logger.error(f"Could not convert streams_raster_view to a savable NumPy array.")
                data_to_save = None

            if data_to_save is not None:
                with rasterio.open(streams_path, 'w', **profile) as dst:
                    dst.write(data_to_save, 1)
                logger.info(f"Streams raster saved to {streams_path}")
    except Exception as e:
        logger.error(f"Error obtaining or saving 'streams' data: {e}", exc_info=True)
        raise
    finally:
        grid.nodata = grid_nodata_backup_streams
        grid.dtype = grid_dtype_backup_streams
        logger.debug(f"Restored grid.nodata to: {grid.nodata}, grid.dtype to: {grid.dtype}")
else:
    logger.warning("Skipping stream extraction as acc_raster_view was not obtained or is None.")
    exit("Stream extraction failed.")

logger.info("Processing attempt finished. Moving to Interfluve Analysis.")
# ... (Interfluve analysis part from your original script, ensuring it uses streams_numpy_array)

# Ensure streams_numpy_array is defined from streams_raster_view before this section
if streams_raster_view is not None:
    if hasattr(streams_raster_view, 'filled'):
        streams_numpy_array = streams_raster_view.filled(0).astype(np.uint8)
    elif isinstance(streams_raster_view, np.ndarray):
        streams_numpy_array = streams_raster_view.astype(np.uint8)
    else:
        logger.error("streams_raster_view is invalid for interfluve analysis.")
        exit("Cannot proceed to interfluve analysis.")
else:
    logger.error("streams_raster_view is None, cannot proceed to interfluve analysis.")
    exit("Stream network data is not available for interfluve analysis.")

# --- 4. Identify Interfluve Zones ---
# (Copied from your original script, assuming streams_numpy_array is correctly populated)
logger.info("Calculating distance from streams...")
binary_streams = (streams_numpy_array > 0).astype(np.uint8)
distance_to_streams = distance_transform_edt(1 - binary_streams)
distance_interfluve_threshold_pixels = 15
interfluves_by_distance = (distance_to_streams > distance_interfluve_threshold_pixels).astype(np.uint8)

interfluves_dist_path = os.path.join(output_dir, 'interfluves_by_distance_gee.tif')
profile_uint8_nodata0 = { # Define a suitable profile for these binary outputs
    'driver': 'GTiff', 'dtype': rasterio.uint8, 'nodata': 0,
    'width': grid.shape[1], 'height': grid.shape[0], 'count': 1,
    'crs': grid.crs, 'transform': grid.affine, 'compress': 'lzw'
}
with rasterio.open(interfluves_dist_path, 'w', **profile_uint8_nodata0) as dst:
    dst.write(interfluves_by_distance, 1)
logger.info(f"Interfluves by distance saved to {interfluves_dist_path}")


logger.info("Calculating TPI...")
if hasattr(dem_raster_view, 'filled'):
    dem_numpy_array_for_tpi = dem_raster_view.filled(grid.nodata.item()).astype(np.float32)
elif isinstance(dem_raster_view, np.ndarray):
    dem_numpy_array_for_tpi = dem_raster_view.astype(np.float32)
else:
    logger.error("Could not get NumPy array from dem_raster_view for TPI.")
    exit("Failed to get DEM NumPy array for TPI.")

tpi_profile_base = {
    'driver': 'GTiff', 'width': grid.shape[1], 'height': grid.shape[0],
    'count': 1, 'crs': grid.crs, 'transform': grid.affine, 'compress': 'lzw'
}
kernel_size = 9
pad_width = kernel_size // 2
# Ensure grid.nodata.item() is used if grid.nodata is a numpy scalar
dem_nodata_val_for_tpi = grid.nodata.item() if hasattr(grid.nodata, 'item') else grid.nodata
dem_array_no_nan = np.nan_to_num(dem_numpy_array_for_tpi, nan=np.nanmean(dem_numpy_array_for_tpi[dem_numpy_array_for_tpi != dem_nodata_val_for_tpi]))

dem_padded = np.pad(dem_array_no_nan, pad_width, mode='reflect')

def mean_filter_nan_aware(arr):
    valid_arr = arr[~np.isnan(arr)]
    if valid_arr.size == 0: return np.nan
    return np.mean(valid_arr)

mean_elevation_neighborhood = generic_filter(
    dem_padded, mean_filter_nan_aware, size=kernel_size, mode='constant', cval=np.nan
)
mean_elevation_neighborhood = mean_elevation_neighborhood[pad_width:-pad_width, pad_width:-pad_width]

tpi = dem_numpy_array_for_tpi - mean_elevation_neighborhood
tpi_interfluve_threshold = 0.5
interfluves_by_tpi = np.where(np.isnan(tpi), 0, (tpi > tpi_interfluve_threshold)).astype(np.uint8)

tpi_path = os.path.join(output_dir, 'tpi_gee.tif')
interfluves_tpi_path = os.path.join(output_dir, 'interfluves_by_tpi_gee.tif')

tpi_profile_out = tpi_profile_base.copy()
tpi_profile_out.update(dtype=rasterio.float32, nodata=np.float32(np.nan))
with rasterio.open(tpi_path, 'w', **tpi_profile_out) as dst:
    dst.write(tpi.astype(rasterio.float32), 1)

interfluve_tpi_profile_out = profile_uint8_nodata0.copy() # Use the uint8 profile
with rasterio.open(interfluves_tpi_path, 'w', **interfluve_tpi_profile_out) as dst:
    dst.write(interfluves_by_tpi, 1)
logger.info(f"TPI saved to {tpi_path}")
logger.info(f"Interfluves by TPI saved to {interfluves_tpi_path}")

logger.info("Combining distance and TPI methods for interfluves...")
if interfluves_by_distance.shape == interfluves_by_tpi.shape:
    combined_interfluves = (interfluves_by_distance & interfluves_by_tpi).astype(np.uint8)
    combined_interfluves_path = os.path.join(output_dir, 'combined_interfluves_gee.tif')
    with rasterio.open(combined_interfluves_path, 'w', **profile_uint8_nodata0) as dst: # Use uint8 profile
        dst.write(combined_interfluves, 1)
    logger.info(f"Combined interfluves saved to {combined_interfluves_path}")
else:
    logger.warning("Shapes of distance and TPI interfluve arrays do not match. Skipping combination.")

logger.info("Processing complete. Check the output_data_gee directory.")