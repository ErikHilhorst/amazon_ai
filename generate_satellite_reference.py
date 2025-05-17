import folium
import rasterio
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService # For Selenium 4+

# --- Configuration ---
project_base_dir = os.path.dirname(os.path.abspath(__file__))
processed_tiffs_dir = os.path.join(project_base_dir, 'output_data_gee_wbt')
# Use the WBT-compatible DEM to get the bounds, as it's the primary input extent
# or your original actual_dem_path_abs if you prefer
reference_tiff_path = os.path.join(processed_tiffs_dir, 'gee_srtm_aoi_wbt_compat.tif') 
# Fallback if the above is not yet created (e.g. during testing)
# reference_tiff_path = os.path.join(project_base_dir, 'output_data_gee', 'gee_srtm_aoi.tif')


output_images_dir = os.path.join(project_base_dir, 'output_images') # Same dir as other visualizations
os.makedirs(output_images_dir, exist_ok=True)
output_html_map = os.path.join(output_images_dir, "reference_satellite_map.html")
output_png_image = os.path.join(output_images_dir, "reference_satellite_image.png")

# Path to your ChromeDriver executable
# OPTION 1: If chromedriver.exe is in your PATH, you might not need to specify this.
# OPTION 2: Provide the full path. Replace with your actual path.
# Make sure the chromedriver version matches your Chrome browser version.
CHROME_DRIVER_PATH = r"C:\Users\larry\Downloads\chrome-win64\chrome.exe" # <--- !!! UPDATE THIS PATH !!!
# If you don't have chromedriver or don't want to use Selenium, set USE_SELENIUM to False
USE_SELENIUM = True # Set to False to just generate HTML and skip screenshot

# --- Get Bounding Box from Reference TIFF ---
def get_raster_bounds(tiff_path):
    if not os.path.exists(tiff_path):
        print(f"Error: Reference TIFF not found at {tiff_path}")
        return None
    try:
        with rasterio.open(tiff_path) as src:
            # Bounds are (minx, miny, maxx, maxy) in the raster's CRS
            # We need to ensure these are in WGS84 (lat/lon) for Folium
            if src.crs.is_geographic:
                bounds = src.bounds
                # Folium expects bounds as [[south_lat, west_lon], [north_lat, east_lon]]
                # src.bounds gives (west_lon, south_lat, east_lon, north_lat)
                folium_bounds = [[bounds.bottom, bounds.left], [bounds.top, bounds.right]]
                print(f"Raster geographic bounds (lat/lon): {folium_bounds}")
                return folium_bounds
            else:
                # If projected, transform to WGS84 (EPSG:4326)
                from rasterio.warp import transform_bounds
                wgs84_bounds = transform_bounds(src.crs, {'init': 'epsg:4326'}, *src.bounds)
                # wgs84_bounds gives (west_lon, south_lat, east_lon, north_lat)
                folium_bounds = [[wgs84_bounds[1], wgs84_bounds[0]], [wgs84_bounds[3], wgs84_bounds[2]]]
                print(f"Raster projected bounds transformed to WGS84 (lat/lon): {folium_bounds}")
                return folium_bounds
    except Exception as e:
        print(f"Error reading bounds from {tiff_path}: {e}")
        return None

# --- Main Script ---
if __name__ == "__main__":
    raster_extent_bounds = get_raster_bounds(reference_tiff_path)

    if not raster_extent_bounds:
        print("Could not determine raster bounds. Exiting.")
        exit()

    # Create a folium.Map object
    google_satellite_tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
    google_attribution = "Google Satellite"

    m = folium.Map(
        tiles=google_satellite_tiles,
        attr=google_attribution
    )

    # Fit map to the raster's bounds
    m.fit_bounds(raster_extent_bounds)

    # --- Optional: Add your areas_data and São Francisco marker if desired for context ---
    sao_francisco_coords = [-12.051333, -63.567164]
    sao_francisco_name = "São Francisco do Guaporé"
    areas_data = [
        {"name": "Area 1", "bounds": [[-12.59, -63.39], [-12.41, -63.21]], "center": [-12.50, -63.30], "color": "blue", "description": "Interfluve Guaporé/São Miguel, near BR-429"},
        {"name": "Area 2", "bounds": [[-11.79, -63.09], [-11.61, -62.91]], "center": [-11.70, -63.00], "color": "green", "description": "Interfluve São Miguel/Cautário, near Seringueiras"},
        {"name": "Area 3", "bounds": [[-12.24, -63.47], [-12.06, -63.29]], "center": [-12.15, -63.38], "color": "red", "description": "Headwaters east of São Francisco do Guaporé"}
    ]

    for area in areas_data:
        folium.Rectangle(bounds=area["bounds"], color=area["color"], fill=True, fill_color=area["color"], fill_opacity=0.1, tooltip=f"<b>{area['name']}</b>").add_to(m)
    folium.Marker(location=sao_francisco_coords, tooltip=sao_francisco_name, icon=folium.Icon(color='orange')).add_to(m)
    # --- End Optional Additions ---

    # Save the map to an HTML file (always useful)
    m.save(output_html_map)
    print(f"Satellite map focused on raster extent saved to {output_html_map}")

    # Capture screenshot using Selenium
    if USE_SELENIUM:
        # Check if CHROME_DRIVER_PATH is set and valid
        if not os.path.exists(CHROME_DRIVER_PATH) and CHROME_DRIVER_PATH != r"C:\path\to\your\chromedriver.exe": # Allow placeholder if not found
             # Try to find chromedriver in PATH if specific path not valid
            from shutil import which
            if which('chromedriver'):
                 print("Using chromedriver found in PATH.")
                 # For Selenium 4, service object is preferred
                 chrome_service = ChromeService() # Will use chromedriver from PATH
            else:
                print(f"Error: ChromeDriver not found at specified path '{CHROME_DRIVER_PATH}' or in system PATH.")
                print("Please install ChromeDriver, update CHROME_DRIVER_PATH, or set USE_SELENIUM = False.")
                exit()
        elif CHROME_DRIVER_PATH == r"C:\path\to\your\chromedriver.exe":
            print(f"Error: Placeholder CHROME_DRIVER_PATH is set. Please update it or ensure chromedriver is in PATH.")
            print("Skipping screenshot generation.")
            exit()
        else: # CHROME_DRIVER_PATH is set and exists
            chrome_service = ChromeService(executable_path=CHROME_DRIVER_PATH)


        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run Chrome in headless mode (no GUI)
        chrome_options.add_argument("--disable-gpu") # Often needed for headless
        # Define window size - this will affect the screenshot.
        # Try to make it somewhat square or match the aspect ratio of your DEM if known.
        # Your DEM is 3711 W x 3713 H, which is almost square.
        # Larger window size = higher resolution screenshot, but also larger file and more memory.
        chrome_options.add_argument("--window-size=1200,1200") # Adjust as needed
        chrome_options.add_argument("--hide-scrollbars")


        # Initialize WebDriver
        driver = None
        try:
            driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
            
            # Open the local HTML file
            html_file_url = 'file:///' + os.path.abspath(output_html_map).replace('\\', '/')
            driver.get(html_file_url)

            # Give the map tiles time to load - this is crucial!
            # Increase if your internet is slow or map is complex.
            time.sleep(10)  # Wait 10 seconds for tiles to load

            # Take screenshot
            driver.save_screenshot(output_png_image)
            print(f"Screenshot saved to {output_png_image}")

        except Exception as e:
            print(f"Error during Selenium screenshot: {e}")
            if "session not created" in str(e).lower() or "executable needs to be in path" in str(e).lower():
                print("This might be due to an incorrect ChromeDriver path or version incompatibility.")
                print(f"Ensure '{CHROME_DRIVER_PATH}' is correct and matches your Chrome browser version.")
            elif "DevToolsActivePort file doesn't exist" in str(e):
                print("This can sometimes happen with headless Chrome. Try with a visible browser first (remove --headless) or ensure all Chrome processes are closed.")

        finally:
            if driver:
                driver.quit()
    else:
        print("Selenium screenshotting is disabled. Open the HTML file manually to view the map.")