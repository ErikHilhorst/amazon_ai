import folium
import ee
import os
import json # For GeoJSON inspection if needed
from dotenv import load_dotenv # Import load_dotenv

# --- Load Environment Variables ---
load_dotenv() # Load variables from .env file into environment
gcp_project_id = os.getenv('GCP_PROJECT_ID') # Get your GCP Project ID

# --- Earth Engine Initialization ---
try:
    if not gcp_project_id:
        print("ERROR: GCP_PROJECT_ID not found in environment variables.")
        print("Please ensure it is set in your .env file or system environment.")
        exit()

    # Initialize with the Google Cloud Project ID
    ee.Initialize(project=gcp_project_id, opt_url='https://earthengine-highvolume.googleapis.com')
    print(f"Google Earth Engine initialized successfully with project: {gcp_project_id}.")

except ee.EEException as e:
    print(f"ERROR: Could not initialize Google Earth Engine with project '{gcp_project_id}'.")
    print(f"Details: {e}")
    if "not found" in str(e) or "verify the project ID" in str(e):
        print(f"Please double-check that '{gcp_project_id}' is a valid Google Cloud Project ID and that the Earth Engine API is enabled for it.")
    if "user does not have access" in str(e):
         print("Please ensure your authenticated user has permissions (e.g., Earth Engine User, Viewer) on this GCP project.")
    # Attempt to authenticate if initialization fails (might not always resolve project issues but good for user auth)
    try:
        print("\nAttempting user authentication (this may open a browser window or prompt for a code)...")
        ee.Authenticate() # This will guide you through authentication if not already done.
        # Retry initialization after authentication
        ee.Initialize(project=gcp_project_id, opt_url='https://earthengine-highvolume.googleapis.com')
        print(f"Google Earth Engine initialized successfully with project '{gcp_project_id}' after re-authentication attempt.")
    except Exception as auth_e:
        print(f"Secondary authentication/initialization attempt failed: {auth_e}")
        print("Please ensure you have run 'earthengine authenticate' in your terminal and followed the prompts,")
        print("and that the GCP_PROJECT_ID is correct and has Earth Engine API enabled.")
        exit() # Exit if EE cannot be initialized, as it's critical.
except Exception as general_e:
    print(f"An unexpected error occurred during Earth Engine initialization: {general_e}")
    exit()


# --- Configuration ---
# Handle project base directory for script or notebook environments
project_base_dir = None # Initialize
try:
    project_base_dir = os.path.dirname(os.path.abspath(__file__))
except NameError: # __file__ is not defined, likely in a notebook or interactive session
    project_base_dir = os.getcwd() # Default to current working directory
    print(f"Running in notebook/interactive mode, project_base_dir set to: {project_base_dir}")
# Though project_base_dir might not be used for explicit path joining later,
# some libraries or implicit behaviors might still rely on the script's perceived location.
# It's safer to keep its determination logic for now.

output_html_map = "output_data/maps/amazon_aoi_with_gedi_coverage.html"
os.makedirs(os.path.dirname(output_html_map), exist_ok=True)

# Path to your GeoJSON file for country borders
country_borders_geojson_path = "input_data/ne_10m_admin_0_countries.geojson"

# Your AOI coordinates (lon, lat)
aoi_coordinates_lon_lat = [
    [-63.8, -13.0],
    [-62.8, -13.0],
    [-62.8, -12.0],
    [-63.8, -12.0],
    [-63.8, -13.0]
]

# --- Calculate Center and Bounds for Folium map based on AOI ---
min_lon_aoi = min(coord[0] for coord in aoi_coordinates_lon_lat)
max_lon_aoi = max(coord[0] for coord in aoi_coordinates_lon_lat)
min_lat_aoi = min(coord[1] for coord in aoi_coordinates_lon_lat)
max_lat_aoi = max(coord[1] for coord in aoi_coordinates_lon_lat)
map_fit_bounds_aoi = [[min_lat_aoi, min_lon_aoi], [max_lat_aoi, max_lon_aoi]] # For folium.fit_bounds
center_lat_aoi = (min_lat_aoi + max_lat_aoi) / 2
center_lon_aoi = (min_lon_aoi + max_lon_aoi) / 2

# --- GEDI Data Processing with Earth Engine ---
amazon_roi_ee = ee.Geometry.Rectangle([-80, -20, -45, 10]) # [lon_min, lat_min, lon_max, lat_max]
gedi_l2a_monthly_collection = ee.ImageCollection("LARSE/GEDI/GEDI02_A_002_MONTHLY")
gedi_coverage_quality_mosaic = gedi_l2a_monthly_collection \
    .filterBounds(amazon_roi_ee) \
    .select('quality_flag') \
    .mosaic()
gedi_binary_coverage = gedi_coverage_quality_mosaic.eq(1).selfMask()
gedi_vis_params = {
    'palette': ['00AA00'],
    'opacity': 0.6
}
gedi_tiles_url = None
try:
    gedi_map_id_object = gedi_binary_coverage.getMapId(gedi_vis_params)
    gedi_tiles_url = gedi_map_id_object['tile_fetcher'].url_format
    print("GEDI coverage layer processed by Earth Engine and tile URL obtained.")
except Exception as e:
    print(f"Error getting GEDI layer from Earth Engine: {e}")
    print("The map will be generated without the GEDI layer.")


# --- Main Folium Map Script ---
if __name__ == "__main__":
    if not os.path.exists(country_borders_geojson_path):
        print(f"WARNING: Country borders GeoJSON file not found at: {country_borders_geojson_path}")
        print("The map will be generated without country borders.")

    m = folium.Map(
        location=[center_lat_aoi, center_lon_aoi],
        zoom_start=8,
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite"
    )
    folium.TileLayer(
        tiles="OpenStreetMap",
        attr='OpenStreetMap',
        name='OpenStreetMap',
        overlay=False,
        control=True
    ).add_to(m)

    if gedi_tiles_url:
        folium.TileLayer(
            tiles=gedi_tiles_url,
            attr='GEDI L2A Monthly Coverage (25m, Quality Flag = 1) via Google Earth Engine',
            name='GEDI LiDAR Coverage (LARSE)',
            overlay=True,
            control=True,
            opacity=gedi_vis_params['opacity']
        ).add_to(m)
        print("GEDI LiDAR coverage layer added to Folium map.")
    else:
        print("GEDI LiDAR coverage layer was not added due to an earlier error or it not being processed.")

    if os.path.exists(country_borders_geojson_path):
        try:
            def style_function_borders(feature):
                return {
                    'fillOpacity': 0,
                    'weight': 1.5,
                    'color': '#FFFF00'
                }
            borders_overlay = folium.GeoJson(
                country_borders_geojson_path,
                name="Country Borders",
                style_function=style_function_borders
            )
            borders_overlay.add_to(m)
            print("Country borders GeoJSON layer added to Folium map.")
        except Exception as e:
            print(f"Could not load or add Country Borders GeoJSON layer: {e}")
    else:
        print(f"Country borders GeoJSON file not found at '{country_borders_geojson_path}', skipping this layer.")

    aoi_coordinates_lat_lon_folium = [(lat, lon) for lon, lat in aoi_coordinates_lon_lat]
    folium.Polygon(
        locations=aoi_coordinates_lat_lon_folium,
        color='red',
        weight=2,
        fill=True,
        fill_color='red',
        fill_opacity=0.15,
        tooltip="Your Area of Interest (AOI)"
    ).add_to(m)
    print("User AOI polygon added to Folium map.")

    m.fit_bounds(map_fit_bounds_aoi)
    folium.LayerControl(collapsed=False).add_to(m)

    try:
        m.save(output_html_map)
        print(f"Map successfully saved to {output_html_map}")
        print(f"Note: GEDI coverage is derived from the LARSE/GEDI/GEDI02_A_002_MONTHLY Earth Engine asset,")
        print("showing areas where the 'l2a_quality_flag' is 1 (indicating good quality rasterized footprints at 25m).")
    except Exception as e:
        print(f"Error saving map to HTML: {e}")

    print("\nScript finished.")
    print("If the GEDI layer is missing or the map is not as expected, please review any error messages above,")
    print("especially regarding Earth Engine initialization and GeoJSON file paths.")
