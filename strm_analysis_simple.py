import pysheds
from pysheds.grid import Grid
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from scipy.ndimage import generic_filter, distance_transform_edt
import matplotlib.pyplot as plt
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

logger.info(f"Starting PySheds (sGrid - flowdir.nodata=None for acc) using: {actual_dem_path_for_pysheds}")

grid = Grid()
logger.debug(f"Initial grid.nodata: {grid.nodata} (type: {type(grid.nodata)})")

dem_raster_view = grid.read_raster(actual_dem_path_for_pysheds, data_name='dem')
logger.info(f"DEM loaded. Type: {type(dem_raster_view)}")
logger.debug(f"dem_raster_view properties: dtype={dem_raster_view.dtype}, nodata={getattr(dem_raster_view, 'nodata', 'N/A')}")

# Set grid.nodata from the input DEM (important for fill_depressions context)
if hasattr(dem_raster_view, 'nodata') and dem_raster_view.nodata is not None:
    grid.nodata = dem_raster_view.nodata
else: # Fallback for SRTM int16 if needed
    if dem_raster_view.dtype == np.int16: grid.nodata = np.int16(-32768)
    else: grid.nodata = np.array(0, dtype=dem_raster_view.dtype).item() if dem_raster_view.dtype else 0
logger.info(f"Grid properties after read_raster: Nodata={grid.nodata} (type: {type(grid.nodata)})")


logger.info("Filling depressions...")
flooded_dem_raster_view = grid.fill_depressions(dem=dem_raster_view, out_name='flooded_dem')
logger.info(f"Depressions filled. Output type: {type(flooded_dem_raster_view)}")
logger.debug(f"flooded_dem_raster_view properties: dtype={flooded_dem_raster_view.dtype}, nodata={getattr(flooded_dem_raster_view, 'nodata', 'N/A')}")


logger.info("Calculating flow direction...")
fdir_raster_view = None
if flooded_dem_raster_view is not None:
    grid_nodata_backup_fdir = grid.nodata # Backup main grid nodata
    # For flowdir output, its sview.Raster is created using main grid's current nodata context.
    # We will set nodata_out=None for fdir_raster_view itself.
    # The temporary grid.nodata is for the sview.Raster constructor of fdir output.
    # If fdir output data itself does not have nodata, then grid.nodata=None might be best.
    
    logger.debug(f"Temporarily setting grid.nodata to None for FLOWDIR output context.")
    grid.nodata = None # Try None for the output viewfinder context
    try:
        # Set nodata_out=None for the fdir_raster_view's own .nodata attribute
        fdir_raster_view = grid.flowdir(dem=flooded_dem_raster_view, out_name='fdir', nodata_out=None)
        logger.info(f"Flow direction calculated. Output type: {type(fdir_raster_view)}")
        logger.debug(f"fdir_raster_view properties: dtype={fdir_raster_view.dtype}, nodata={getattr(fdir_raster_view, 'nodata', 'N/A')}")
        # We expect fdir_raster_view.nodata to be None
    except Exception as e:
        logger.error(f"Error during grid.flowdir: {e}", exc_info=True)
        raise
    finally:
        grid.nodata = grid_nodata_backup_fdir # Restore
        logger.debug(f"Restored grid.nodata to: {grid.nodata} (type: {type(grid.nodata)})")
else:
    logger.error("Flooded DEM is None.")
    exit()


logger.info("Calculating flow accumulation...")
acc_raster_view = None
if fdir_raster_view is not None:
    logger.debug(f"Input to accumulation (fdir_raster_view): dtype={fdir_raster_view.dtype}, nodata={getattr(fdir_raster_view, 'nodata', 'N/A')}")
    # Accumulation output sview.Raster uses fdir_raster_view.viewfinder.
    # If fdir_raster_view.nodata is None, the np.can_cast check in sview.Raster.__new__ should be skipped.
    try:
        grid.accumulation(fdir=fdir_raster_view, out_name='acc')
        logger.info(f"Flow accumulation calculated.")
        acc_raster_view = grid.get_data('acc', return_sview=True)
        logger.info(f"Accumulation accessed. Output type: {type(acc_raster_view)}")
        logger.debug(f"acc_raster_view properties: dtype={acc_raster_view.dtype}, nodata={getattr(acc_raster_view, 'nodata', 'N/A')}")
    except Exception as e:
        logger.error(f"Error during/after grid.accumulation: {e}", exc_info=True)
        raise
else:
    logger.error("Flow direction is None.")
    exit()


logger.info("Extracting stream network...")
streams_raster_view = None
if acc_raster_view is not None and fdir_raster_view is not None :
    grid_nodata_backup_streams = grid.nodata
    streams_out_nodata_typed = np.uint8(0)
    
    logger.debug(f"Temporarily setting grid.nodata to {streams_out_nodata_typed} (type {type(streams_out_nodata_typed)}) for STREAMS output context.")
    grid.nodata = streams_out_nodata_typed
    try:
        grid.extract_river_network(fdir=fdir_raster_view, acc=acc_raster_view, threshold=1000, out_name='streams')
        logger.info(f"Stream network extracted.")
        streams_raster_view = grid.get_data('streams', return_sview=True)
        logger.info(f"Streams accessed. Output type: {type(streams_raster_view)}")
        logger.debug(f"streams_raster_view properties: dtype={streams_raster_view.dtype}, nodata={getattr(streams_raster_view, 'nodata', 'N/A')}")
    except Exception as e:
        logger.error(f"Error during/after grid.extract_river_network: {e}", exc_info=True)
        raise
    finally:
        grid.nodata = grid_nodata_backup_streams
        logger.debug(f"Restored grid.nodata to: {grid.nodata} (type: {type(grid.nodata)})")
else:
    logger.error("Accumulation or Flow Direction is None. Cannot extract streams.")
    exit()

if streams_raster_view is not None:
    logger.info("Preparing to save streams raster...")
    streams_numpy_array = None
    intended_streams_nodata_val = streams_out_nodata_typed.item()

    if hasattr(streams_raster_view, 'filled'):
        streams_numpy_array = streams_raster_view.filled(intended_streams_nodata_val).astype(np.uint8)
    elif isinstance(streams_raster_view, np.ndarray):
        streams_numpy_array = streams_raster_view.astype(np.uint8)
    
    if streams_numpy_array is not None:
        streams_path = os.path.join(output_dir, 'streams_gee.tif')
        profile = {
            'driver': 'GTiff', 'dtype': rasterio.uint8, 'nodata': intended_streams_nodata_val,
            'width': grid.shape[1], 'height': grid.shape[0], 'count': 1,
            'crs': grid.crs, 'transform': grid.affine, 'compress': 'lzw'
        }
        with rasterio.open(streams_path, 'w', **profile) as dst:
            dst.write(streams_numpy_array, 1)
        logger.info(f"Streams raster saved to {streams_path}")

        logger.info("Starting Interfluve Analysis...")
        # ... (Interfluve analysis code as in the previous full script) ...
        logger.info("Calculating distance from streams...")
        binary_streams = (streams_numpy_array > 0).astype(np.uint8)
        distance_to_streams = distance_transform_edt(1 - binary_streams)
        distance_interfluve_threshold_pixels = 15
        interfluves_by_distance = (distance_to_streams > distance_interfluve_threshold_pixels).astype(np.uint8)

        interfluves_dist_path = os.path.join(output_dir, 'interfluves_by_distance_gee.tif')
        profile_uint8_nodata0 = profile.copy()
        profile_uint8_nodata0['nodata'] = 0
        profile_uint8_nodata0['dtype'] = rasterio.uint8

        with rasterio.open(interfluves_dist_path, 'w', **profile_uint8_nodata0) as dst:
            dst.write(interfluves_by_distance, 1)
        logger.info(f"Interfluves by distance saved to {interfluves_dist_path}")

        logger.info("Calculating TPI...")
        dem_original_nodata_val = grid.nodata.item() if hasattr(grid.nodata, 'item') else grid.nodata
        
        dem_numpy_array_for_tpi = None
        if hasattr(dem_raster_view, 'filled'):
            dem_numpy_array_for_tpi = dem_raster_view.filled(dem_original_nodata_val).astype(np.float32)
        elif isinstance(dem_raster_view, np.ndarray):
            dem_numpy_array_for_tpi = dem_raster_view.astype(np.float32)
        
        if dem_numpy_array_for_tpi is None:
            logger.error("Could not get NumPy array from dem_raster_view for TPI.")
            exit("Failed to get DEM NumPy array for TPI.")

        tpi_profile_base = {
            'driver': 'GTiff', 'width': grid.shape[1], 'height': grid.shape[0],
            'count': 1, 'crs': grid.crs, 'transform': grid.affine, 'compress': 'lzw'
        }
        kernel_size = 9
        pad_width = kernel_size // 2
        
        dem_mask_for_tpi = (dem_numpy_array_for_tpi == dem_original_nodata_val)
        valid_dem_pixels = dem_numpy_array_for_tpi[~dem_mask_for_tpi]
        dem_mean_for_nan_replacement = np.mean(valid_dem_pixels) if valid_dem_pixels.size > 0 else 0
        dem_array_no_nodata = np.where(dem_mask_for_tpi, dem_mean_for_nan_replacement, dem_numpy_array_for_tpi)
        dem_array_no_nodata = np.nan_to_num(dem_array_no_nodata, nan=dem_mean_for_nan_replacement)
        dem_padded = np.pad(dem_array_no_nodata, pad_width, mode='reflect')

        mean_elevation_neighborhood = generic_filter(
            dem_padded, np.mean, size=kernel_size, mode='reflect'
        )
        mean_elevation_neighborhood = mean_elevation_neighborhood[pad_width:-pad_width, pad_width:-pad_width]

        tpi = dem_numpy_array_for_tpi - mean_elevation_neighborhood
        tpi[dem_mask_for_tpi] = np.nan

        tpi_interfluve_threshold = 0.5
        interfluves_by_tpi = np.where(np.isnan(tpi), 0, (tpi > tpi_interfluve_threshold)).astype(np.uint8)

        tpi_path = os.path.join(output_dir, 'tpi_gee.tif')
        interfluves_tpi_path = os.path.join(output_dir, 'interfluves_by_tpi_gee.tif')
        
        tpi_profile_out = tpi_profile_base.copy()
        tpi_profile_out.update(dtype=rasterio.float32, nodata=np.float32(np.nan))
        with rasterio.open(tpi_path, 'w', **tpi_profile_out) as dst:
            dst.write(tpi.astype(rasterio.float32), 1)

        interfluve_tpi_profile_out = profile_uint8_nodata0.copy()
        with rasterio.open(interfluves_tpi_path, 'w', **interfluve_tpi_profile_out) as dst:
            dst.write(interfluves_by_tpi, 1)
        logger.info(f"TPI saved to {tpi_path}")
        logger.info(f"Interfluves by TPI saved to {interfluves_tpi_path}")

        logger.info("Combining distance and TPI methods for interfluves...")
        if interfluves_by_distance.shape == interfluves_by_tpi.shape:
            combined_interfluves = (interfluves_by_distance & interfluves_by_tpi).astype(np.uint8)
            combined_interfluves_path = os.path.join(output_dir, 'combined_interfluves_gee.tif')
            with rasterio.open(combined_interfluves_path, 'w', **profile_uint8_nodata0) as dst:
                dst.write(combined_interfluves, 1)
            logger.info(f"Combined interfluves saved to {combined_interfluves_path}")
        else:
            logger.warning("Shapes of distance and TPI interfluve arrays do not match. Skipping combination.")

    else:
        logger.error("Failed to prepare streams_numpy_array. Cannot save or do interfluve analysis.")
else:
    logger.error("streams_raster_view is None. Processing halted before saving streams.")

logger.info("Processing complete. Check the output_data_gee directory.")