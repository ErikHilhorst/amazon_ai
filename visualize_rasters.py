import rasterio
import matplotlib.pyplot as plt
import numpy as np
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
project_base_dir = os.path.dirname(os.path.abspath(__file__))
processed_tiffs_dir = os.path.join(project_base_dir, 'output_data_gee_wbt')
output_images_dir = os.path.join(project_base_dir, 'output_images')
os.makedirs(output_images_dir, exist_ok=True)

# --- Helper Function to Plot and Save ---
def visualize_raster(tiff_path, output_image_path, title, cmap='viridis', vmin_user=None, vmax_user=None, is_binary=False, log_scale_facc=False):
    """
    Reads a GeoTIFF, visualizes it, and saves it as a PNG.
    Uses vmin_user and vmax_user for user-specified limits.
    """
    if not os.path.exists(tiff_path):
        logger.error(f"TIFF file not found: {tiff_path}")
        return

    try:
        with rasterio.open(tiff_path) as src:
            data = src.read(1)
            nodata_val = src.nodatavals[0] if src.nodatavals else None

            if nodata_val is not None:
                if np.issubdtype(data.dtype, np.floating) and np.isnan(nodata_val):
                    masked_data = np.ma.masked_where(np.isnan(data), data)
                else:
                    masked_data = np.ma.masked_equal(data, nodata_val)
            else:
                masked_data = data

            fig, ax = plt.subplots(1, 1, figsize=(12, 10)) # Slightly wider for colorbar
            
            current_vmin = vmin_user
            current_vmax = vmax_user

            if is_binary:
                im = ax.imshow(masked_data, cmap='gray_r', vmin=0, vmax=1)
            elif log_scale_facc and 'facc' in tiff_path.lower():
                # Apply log transformation for flow accumulation
                # Fill masked (nodata) values with 0 before log1p to avoid issues with mask
                plot_data_log = np.log1p(np.maximum(0, masked_data.filled(0))) 
                
                # If vmin_user/vmax_user not specified for FACC, calculate from percentiles
                if vmin_user is None or vmax_user is None:
                    # Calculate percentiles on the log-transformed data, excluding true zeros if they dominate
                    valid_log_data = plot_data_log[plot_data_log > np.log1p(0) + 1e-9] # Exclude values very close to log1p(0)
                    if valid_log_data.size > 20: # Ensure enough data points for robust percentiles
                        current_vmin = np.percentile(valid_log_data, 2)  # e.g., 2nd percentile as min
                        current_vmax = np.percentile(valid_log_data, 98) # e.g., 98th percentile as max
                        # Ensure vmin is not greater than vmax (can happen if data is very flat)
                        if current_vmin >= current_vmax :
                            current_vmin = valid_log_data.min()
                            current_vmax = valid_log_data.max()
                        if current_vmin == current_vmax: # If still equal (e.g. mostly one value) add a small range
                            current_vmax = current_vmin + 1 
                    elif plot_data_log.size > 0 : # Fallback for fewer points
                        current_vmin = plot_data_log.min()
                        current_vmax = plot_data_log.max()
                        if current_vmin == current_vmax:
                            current_vmax = current_vmin + 1
                    else: # All data was zero or nodata
                        current_vmin = np.log1p(0)
                        current_vmax = np.log1p(1)
                    logger.debug(f"FACC '{title}': auto vmin_log={current_vmin:.2f}, vmax_log={current_vmax:.2f}")

                im = ax.imshow(plot_data_log, cmap=cmap, vmin=current_vmin, vmax=current_vmax)
            else:
                im = ax.imshow(masked_data, cmap=cmap, vmin=current_vmin, vmax=current_vmax)
            
            ax.set_title(title, fontsize=14)
            ax.set_axis_off()
            
            # Add colorbar
            # Create an axes for the colorbar on the right side
            from mpl_toolkits.axes_grid1 import make_axes_locatable
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="5%", pad=0.1)
            cb = fig.colorbar(im, cax=cax)
            cb.ax.tick_params(labelsize=10)


            plt.tight_layout(rect=[0, 0, 0.95, 1]) # Adjust rect to prevent title overlap with suptitle if used
            plt.savefig(output_image_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"Saved visualization: {output_image_path}")

    except Exception as e:
        logger.error(f"Failed to visualize {tiff_path}: {e}", exc_info=True)

# --- List of TIFFs to Visualize ---
tiffs_to_visualize = [
    {"name": "gee_srtm_aoi_wbt_compat.tif", "title": "WBT-Compatible DEM (Input)", "cmap": "terrain"},
    {"name": "filled_dem_wbt.tif", "title": "Filled DEM", "cmap": "terrain"},
    {"name": "d8_pointer_wbt.tif", "title": "D8 Flow Pointers", "cmap": "viridis"},
    {"name": "facc_wbt.tif", "title": "Flow Accumulation (Log Scale)", "cmap": "Blues", "log_scale_facc": True}, # vmin/vmax will be auto-calculated
    {"name": "streams_gee_wbt_final.tif", "title": "Final Extracted Streams", "is_binary": True},
    {"name": "interfluves_by_distance_gee_wbt.tif", "title": "Interfluves by Distance", "is_binary": True},
    {"name": "tpi_gee_wbt.tif", "title": "Topographic Position Index (TPI)", "cmap": "RdBu_r", "vmin_user":-2, "vmax_user":2},
    {"name": "interfluves_by_tpi_gee_wbt.tif", "title": "Interfluves by TPI", "is_binary": True},
    {"name": "combined_interfluves_gee_wbt.tif", "title": "Combined Interfluves", "is_binary": True},
]

# --- Main Loop ---
if __name__ == "__main__":
    logger.info(f"Looking for TIFFs in: {processed_tiffs_dir}")
    logger.info(f"Saving output images to: {output_images_dir}")

    for item in tiffs_to_visualize:
        tiff_file_path = os.path.join(processed_tiffs_dir, item["name"])
        output_png_path = os.path.join(output_images_dir, os.path.splitext(item["name"])[0] + ".png")
        
        visualize_raster(
            tiff_file_path,
            output_png_path,
            item["title"],
            cmap=item.get("cmap", 'viridis'),
            vmin_user=item.get("vmin_user"), # Pass user-defined vmin
            vmax_user=item.get("vmax_user"), # Pass user-defined vmax
            is_binary=item.get("is_binary", False),
            log_scale_facc=item.get("log_scale_facc", False)
        )
    
    logger.info("Visualization script finished.")