import folium
import rasterio
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from scipy.ndimage import binary_dilation # For dilation

# --- Configuration ---
reference_dem_tiff_path = "output_data/processed_dem/gee_srtm_aoi_wbt_compat.tif"
overlay_tiff_path = "output_data/interfluves/combined_interfluves_gee_wbt.tif"

output_html_map = "output_data/maps/satellite_map_with_enhanced_overlay.html"
output_png_image = "output_data/maps/satellite_map_with_enhanced_overlay.png"
temp_overlay_png_path = "output_data/intermediate_outputs/temp_enhanced_overlay.png"
os.makedirs(os.path.dirname(output_html_map), exist_ok=True) # For maps
os.makedirs(os.path.dirname(temp_overlay_png_path), exist_ok=True) # For intermediate_outputs

CHROME_DRIVER_PATH = r"C:\Users\larry\Downloads\chromedriver-win64\chromedriver.exe" # <--- !!! UPDATE THIS PATH !!!
USE_SELENIUM = False

# --- Get Bounding Box (same as before) ---
def get_raster_bounds(tiff_path):
    # ... (keep the existing get_raster_bounds function)
    if not os.path.exists(tiff_path):
        print(f"Error: Reference TIFF not found at {tiff_path}")
        return None
    try:
        with rasterio.open(tiff_path) as src:
            if src.crs.is_geographic:
                bounds = src.bounds
                folium_bounds = [[bounds.bottom, bounds.left], [bounds.top, bounds.right]]
                # print(f"Raster geographic bounds (lat/lon) for {os.path.basename(tiff_path)}: {folium_bounds}")
                return folium_bounds
            else:
                from rasterio.warp import transform_bounds
                wgs84_bounds = transform_bounds(src.crs, {'init': 'epsg:4326'}, *src.bounds)
                folium_bounds = [[wgs84_bounds[1], wgs84_bounds[0]], [wgs84_bounds[3], wgs84_bounds[2]]]
                # print(f"Raster projected bounds for {os.path.basename(tiff_path)} transformed to WGS84 (lat/lon): {folium_bounds}")
                return folium_bounds
    except Exception as e:
        print(f"Error reading bounds from {tiff_path}: {e}")
        return None

# --- Create RGBA PNG for Folium Overlay with Dilation ---
def create_enhanced_overlay_png(source_tiff_path, target_png_path,
                                color=(255, 0, 255), # Bright Magenta
                                alpha=200,          # More opaque (0-255)
                                dilation_iterations=3, # Number of pixels to dilate by. 2 = 5x5 window effectively.
                                nodata_val=0):
    """
    Creates a PNG from a single-band GeoTIFF for overlay, with dilation for binary features.
    For TPI or continuous data, dilation is usually not desired, so it's skipped.
    """
    if not os.path.exists(source_tiff_path):
        print(f"Error: Overlay source TIFF not found at {source_tiff_path}")
        return False
    try:
        with rasterio.open(source_tiff_path) as src:
            data = src.read(1)
            height, width = data.shape
            rgba = np.zeros((height, width, 4), dtype=np.uint8) # R, G, B, Alpha

            is_binary_interfluve_map = 'interfluves' in os.path.basename(source_tiff_path) or \
                                     'streams' in os.path.basename(source_tiff_path)

            if is_binary_interfluve_map:
                # Create a binary mask (True where data is 1)
                binary_mask = (data == 1)

                # Apply dilation if iterations > 0
                if dilation_iterations > 0:
                    # The 'iterations' parameter in binary_dilation controls how many times the operation is applied.
                    # A structure can be provided, but a default (cross-shaped structuring element) is fine.
                    # Iterations=1 dilates by 1 pixel. Iterations=2 dilates by 2 pixels etc.
                    # Visually, dilation_iterations=2 will make features about 5 pixels wider (2 on each side + original).
                    dilated_mask = binary_dilation(binary_mask, iterations=dilation_iterations)
                    mask_to_color = dilated_mask
                    print(f"Applied dilation with {dilation_iterations} iterations.")
                else:
                    mask_to_color = binary_mask # No dilation

                rgba[mask_to_color, 0] = color[0]
                rgba[mask_to_color, 1] = color[1]
                rgba[mask_to_color, 2] = color[2]
                rgba[mask_to_color, 3] = alpha
            elif 'tpi' in os.path.basename(source_tiff_path).lower():
                # TPI Handling (as before, no dilation for TPI)
                print("Applying TPI colormap.")
                norm_tpi = plt.Normalize(vmin=-2, vmax=2)
                colormap = plt.cm.RdBu_r
                colored_tpi = colormap(norm_tpi(data))

                alpha_channel_tpi = np.ones_like(data, dtype=float) * (alpha / 255.0)
                alpha_channel_tpi[np.abs(data) < 0.25] = 0.1 * (alpha / 255.0) # Make flats very transparent but relative to overall alpha

                rgba[:,:,0] = (colored_tpi[:,:,0] * 255).astype(np.uint8)
                rgba[:,:,1] = (colored_tpi[:,:,1] * 255).astype(np.uint8)
                rgba[:,:,2] = (colored_tpi[:,:,2] * 255).astype(np.uint8)
                rgba[:,:,3] = (alpha_channel_tpi * 255).astype(np.uint8)

                if src.nodatavals[0] is not None:
                    nodata_mask = np.isnan(data) if np.isnan(src.nodatavals[0]) else (data == src.nodatavals[0])
                    rgba[nodata_mask, 3] = 0
            else: # Generic case (assume binary, apply dilation)
                print("Applying generic binary colormap with dilation.")
                binary_mask = (data != nodata_val)
                if dilation_iterations > 0:
                    dilated_mask = binary_dilation(binary_mask, iterations=dilation_iterations)
                    mask_to_color = dilated_mask
                else:
                    mask_to_color = binary_mask
                rgba[mask_to_color, 0] = color[0]
                rgba[mask_to_color, 1] = color[1]
                rgba[mask_to_color, 2] = color[2]
                rgba[mask_to_color, 3] = alpha

            plt.imsave(target_png_path, rgba)
            print(f"Enhanced overlay PNG created at {target_png_path}")
            return True
    except Exception as e:
        print(f"Error creating enhanced overlay PNG from {source_tiff_path}: {e}")
        return False

# --- Main Script ---
if __name__ == "__main__":
    map_fit_bounds = get_raster_bounds(reference_dem_tiff_path)
    if not map_fit_bounds:
        print("Could not determine DEM bounds for map fitting. Exiting.")
        exit()

    # --- Customize Overlay Appearance ---
    # For 'combined_interfluves_gee_wbt.tif' or other binary interfluve maps:
    overlay_color_binary = (255, 0, 255)  # Bright Magenta (R, G, B)
    overlay_alpha_binary = 200             # Opacity (0-255, higher is more opaque)
    dilation_amount = 6                  # Dilate by 2 pixels. Effectively makes features ~5 pixels wide.
                                         # Set to 0 for no dilation.

    # For TPI (these will be used if overlay_tiff_path points to a TPI map)
    tpi_alpha = 180 # General alpha for TPI, transparency for flat areas is relative to this

    # Determine parameters based on the overlay TIFF name
    if 'interfluves' in os.path.basename(overlay_tiff_path) or \
       'streams' in os.path.basename(overlay_tiff_path) :
        current_color = overlay_color_binary
        current_alpha = overlay_alpha_binary
        current_dilation = dilation_amount
    elif 'tpi' in os.path.basename(overlay_tiff_path).lower():
        current_color = None # Not directly used for TPI as colormap handles it
        current_alpha = tpi_alpha
        current_dilation = 0 # No dilation for TPI
    else: # Default for other unknown binary types
        current_color = (0, 255, 255) # Cyan
        current_alpha = 200
        current_dilation = dilation_amount

    if not create_enhanced_overlay_png(
        overlay_tiff_path,
        temp_overlay_png_path,
        color=current_color,
        alpha=current_alpha,
        dilation_iterations=current_dilation
    ):
        print("Failed to create enhanced overlay PNG. Exiting.")
        exit()

    overlay_raster_bounds = get_raster_bounds(overlay_tiff_path)
    if not overlay_raster_bounds:
        print("Could not determine overlay raster bounds. Exiting.")
        exit()

    google_satellite_tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
    google_attribution = "Google Satellite"
    m = folium.Map(tiles=google_satellite_tiles, attr=google_attribution)
    m.fit_bounds(map_fit_bounds)

    img_overlay = folium.raster_layers.ImageOverlay(
        name=f"Overlay: {os.path.basename(overlay_tiff_path)} (Dilated: {current_dilation}px)",
        image=temp_overlay_png_path,
        bounds=overlay_raster_bounds,
        opacity=1.0, # The alpha is baked into the PNG, so Folium layer opacity can be 1.0
        interactive=True,
        cross_origin=False,
        zindex=1,
        show=True
    )
    img_overlay.add_to(m)
    folium.LayerControl().add_to(m)

    # ... (Optional markers and areas_data) ...

    m.save(output_html_map)
    print(f"Satellite map with enhanced overlay saved to {output_html_map}")

    # ... (Selenium screenshot code, same as before) ...
    if USE_SELENIUM:
        # (Your Selenium code as before)
        # ...
        # Remember to update CHROME_DRIVER_PATH and ensure chromedriver version matches Chrome
        if not os.path.exists(CHROME_DRIVER_PATH) and CHROME_DRIVER_PATH != r"C:\path\to\your\chromedriver.exe":
             from shutil import which
             if which('chromedriver'):
                 print("Using chromedriver found in PATH.")
                 chrome_service = ChromeService()
             else:
                print(f"Error: ChromeDriver not found at specified path '{CHROME_DRIVER_PATH}' or in system PATH.")
                USE_SELENIUM = False # Disable if not found
        elif CHROME_DRIVER_PATH == r"C:\path\to\your\chromedriver.exe":
            print(f"Error: Placeholder CHROME_DRIVER_PATH is set. Please update it or ensure chromedriver is in PATH.")
            USE_SELENIUM = False
        else:
            chrome_service = ChromeService(executable_path=CHROME_DRIVER_PATH)

        if USE_SELENIUM:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1200,1200")
            chrome_options.add_argument("--hide-scrollbars")
            driver = None
            try:
                driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
                html_file_url = 'file:///' + os.path.abspath(output_html_map).replace('\\', '/')
                driver.get(html_file_url)
                time.sleep(10) # Allow map and overlay to load
                driver.save_screenshot(output_png_image)
                print(f"Screenshot saved to {output_png_image}")
            except Exception as e:
                print(f"Error during Selenium screenshot: {e}")
            finally:
                if driver:
                    driver.quit()
    if not USE_SELENIUM:
        print("Selenium screenshotting is disabled or failed. Open the HTML file manually to view the map.")


    # if os.path.exists(temp_overlay_png_path):
    #     os.remove(temp_overlay_png_path)
    #     print(f"Temporary overlay PNG {temp_overlay_png_path} removed.")
