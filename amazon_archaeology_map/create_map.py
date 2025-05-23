import pandas as pd
import numpy as np
import folium
from folium import plugins
from pyproj import Transformer
import rasterio
from rasterio.warp import transform_bounds
import os
import matplotlib.pyplot as plt
from scipy.ndimage import binary_dilation

# --- Configuration ---
project_base_dir = os.path.dirname(os.path.abspath(__file__))
ARCHAEOLOGICAL_DATA_FOLDER = os.path.join(project_base_dir, "data")
MAP_CENTER_ARCH = [-10.0, -67.0]
MAP_ZOOM_ARCH = 4
RASTER_DATA_FOLDER = os.path.join(project_base_dir, 'output_data_gee_wbt')
REFERENCE_BOUNDS_TIFF_PATH = os.path.join(RASTER_DATA_FOLDER, 'gee_srtm_aoi_wbt_compat.tif')
OVERLAY_SOURCE_TIFF_PATH = os.path.join(RASTER_DATA_FOLDER, 'combined_interfluves_gee_wbt.tif') # Ensure this is your interfluve map
OUTPUT_DIR = os.path.join(project_base_dir, 'output_images')
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_HTML_MAP = os.path.join(OUTPUT_DIR, "combined_archaeology_raster_map.html")
TEMP_OVERLAY_PNG_PATH = os.path.join(OUTPUT_DIR, "temp_raster_overlay.png")
OVERLAY_COLOR_BINARY = (255, 0, 255)
OVERLAY_ALPHA_BINARY = 200
DILATION_AMOUNT_BINARY = 3
TPI_ALPHA = 180

# --- Helper: UTM to Lat/Lon ---
def utm_to_latlon(utm_x, utm_y, utm_zone=19, hemisphere='south'):
    utm_crs_code = 32600 + utm_zone if hemisphere == 'north' else 32700 + utm_zone
    utm_crs = f"EPSG:{utm_crs_code}"
    wgs84_crs = "EPSG:4326"
    transformer = Transformer.from_crs(utm_crs, wgs84_crs, always_xy=True)
    lon, lat = transformer.transform(utm_x, utm_y)
    return lat, lon

# --- Archaeological Data Reading Functions ---
def read_arch_data(filepath, source_name, utm_conversion_params=None, lat_col='latitude', lon_col='longitude', extra_processing_func=None):
    try:
        df = pd.read_csv(filepath)
        if utm_conversion_params:
            lats, lons = [], []
            for _, row in df.iterrows():
                if pd.notna(row[utm_conversion_params['x_col']]) and pd.notna(row[utm_conversion_params['y_col']]):
                    lat, lon = utm_to_latlon(
                        row[utm_conversion_params['x_col']],
                        row[utm_conversion_params['y_col']],
                        utm_zone=utm_conversion_params['zone'],
                        hemisphere=utm_conversion_params.get('hemisphere', 'south')
                    )
                    lats.append(lat); lons.append(lon)
                else:
                    lats.append(np.nan); lons.append(np.nan)
            df['latitude'] = lats
            df['longitude'] = lons
        elif lat_col not in df.columns or lon_col not in df.columns:
            if 'y' in df.columns and 'x' in df.columns:
                df['latitude'] = pd.to_numeric(df['y'], errors='coerce')
                df['longitude'] = pd.to_numeric(df['x'], errors='coerce')
            elif 'Latitude' in df.columns and 'Longitude' in df.columns:
                 df['latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
                 df['longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
            else:
                df['latitude'] = np.nan
                df['longitude'] = np.nan
        else:
            df['latitude'] = pd.to_numeric(df[lat_col], errors='coerce')
            df['longitude'] = pd.to_numeric(df[lon_col], errors='coerce')

        if extra_processing_func:
            df = extra_processing_func(df, filepath)

        df['source'] = source_name
        print(f"  - Loaded {len(df)} records for {source_name}. Valid coords: {len(df.dropna(subset=['latitude', 'longitude']))}")
        return df
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}. Skipping {source_name}.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading {source_name} data from {filepath}: {e}")
        return pd.DataFrame()

def process_submit_data(df, filepath):
    if 'x' in df.columns and 'y' in df.columns:
        sample_x = df['x'].iloc[0] if len(df) > 0 else None
        is_lat_lon = False
        if sample_x is not None and isinstance(sample_x, (int, float)) and -180 <= sample_x <= 180:
            if 'y' in df.columns and isinstance(df['y'].iloc[0], (int, float)) and -90 <= df['y'].iloc[0] <= 90:
                is_lat_lon = True
        
        if is_lat_lon:
            df['latitude'] = df['y']
            df['longitude'] = df['x']
        else:
            df['latitude'] = np.nan
            df['longitude'] = np.nan
            for idx, row in df.iterrows():
                if pd.notna(row['x']) and pd.notna(row['y']):
                    for zone in [18, 19, 20, 21, 22]:
                        try:
                            lat, lon = utm_to_latlon(row['x'], row['y'], utm_zone=zone, hemisphere='south')
                            if -90 <= lat <= 90 and -180 <= lon <= 180:
                                df.at[idx, 'latitude'] = lat
                                df.at[idx, 'longitude'] = lon
                                break
                        except: continue
    return df

# --- Helper: Get Raster Bounds ---
def get_raster_bounds(tiff_path):
    if not os.path.exists(tiff_path):
        print(f"Error: Reference TIFF not found at {tiff_path}")
        return None
    try:
        with rasterio.open(tiff_path) as src:
            if src.crs.is_geographic:
                bounds = src.bounds
                folium_bounds = [[bounds.bottom, bounds.left], [bounds.top, bounds.right]]
            else:
                wgs84_bounds = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
                folium_bounds = [[wgs84_bounds[1], wgs84_bounds[0]], [wgs84_bounds[3], wgs84_bounds[2]]]
            print(f"  Bounds for {os.path.basename(tiff_path)} (lat/lon for Folium): {folium_bounds}")
            return folium_bounds
    except Exception as e:
        print(f"Error reading bounds from {tiff_path}: {e}")
        return None

# --- Helper: Create Enhanced Overlay PNG (Updated for specific interfluve handling) ---
def create_enhanced_overlay_png(source_tiff_path, target_png_path,
                                color=(255, 0, 255), alpha=200,
                                dilation_iterations=0, nodata_val=None):
    if not os.path.exists(source_tiff_path):
        print(f"Error: Overlay source TIFF not found at {source_tiff_path}")
        return False
    try:
        with rasterio.open(source_tiff_path) as src:
            data = src.read(1)
            height, width = data.shape
            rgba = np.zeros((height, width, 4), dtype=np.uint8)

            effective_nodata_val_generic = nodata_val
            if effective_nodata_val_generic is None:
                effective_nodata_val_generic = src.nodatavals[0] if src.nodatavals and src.nodatavals[0] is not None else 0

            filename_lower = os.path.basename(source_tiff_path).lower()
            is_interfluves_or_streams = 'interfluves' in filename_lower or 'streams' in filename_lower
            is_tpi = 'tpi' in filename_lower

            if is_interfluves_or_streams:
                print(f"  Applying specific interfluves/streams logic (features are value 1) with dilation: {dilation_iterations} iterations...")
                binary_mask = (data == 1) # Assumes interfluves/streams are value 1

                if dilation_iterations > 0:
                    mask_to_color = binary_dilation(binary_mask, iterations=dilation_iterations)
                    print(f"    Applied dilation with {dilation_iterations} iterations.")
                else:
                    mask_to_color = binary_mask

                if color:
                    rgba[mask_to_color, 0] = color[0]
                    rgba[mask_to_color, 1] = color[1]
                    rgba[mask_to_color, 2] = color[2]
                rgba[mask_to_color, 3] = alpha

            elif is_tpi:
                print("  Applying TPI colormap...")
                tpi_nodata_val = src.nodatavals[0] if src.nodatavals and src.nodatavals[0] is not None else np.nan
                
                valid_data_tpi = data[data != tpi_nodata_val] if not np.isnan(tpi_nodata_val) else data[~np.isnan(data)]
                if len(valid_data_tpi) < 2:
                    vmin_tpi, vmax_tpi = -2, 2
                    if len(valid_data_tpi) == 1: vmin_tpi, vmax_tpi = valid_data_tpi[0]-1, valid_data_tpi[0]+1
                else:
                     vmin_tpi = np.percentile(valid_data_tpi, 5)
                     vmax_tpi = np.percentile(valid_data_tpi, 95)
                if vmin_tpi == vmax_tpi: vmin_tpi -=1; vmax_tpi +=1

                norm_tpi = plt.Normalize(vmin=vmin_tpi, vmax=vmax_tpi)
                colormap = plt.cm.RdBu_r
                colored_tpi = colormap(norm_tpi(data))

                alpha_channel_tpi = np.ones_like(data, dtype=float) * (alpha / 255.0)
                alpha_channel_tpi[np.abs(data) < 0.25] = 0.1 * (alpha / 255.0)

                rgba[:,:,0] = (colored_tpi[:,:,0] * 255).astype(np.uint8)
                rgba[:,:,1] = (colored_tpi[:,:,1] * 255).astype(np.uint8)
                rgba[:,:,2] = (colored_tpi[:,:,2] * 255).astype(np.uint8)
                rgba[:,:,3] = (alpha_channel_tpi * 255).astype(np.uint8)

                nodata_mask_for_tpi = (data == tpi_nodata_val) if not np.isnan(tpi_nodata_val) else np.isnan(data)
                rgba[nodata_mask_for_tpi, 3] = 0

            else: # Generic case
                print(f"  Applying generic binary/single-color logic with dilation: {dilation_iterations} iterations...")
                binary_mask = (data != effective_nodata_val_generic) if not np.isnan(effective_nodata_val_generic) else ~np.isnan(data)

                if dilation_iterations > 0:
                    mask_to_color = binary_dilation(binary_mask, iterations=dilation_iterations)
                    print(f"    Applied dilation with {dilation_iterations} iterations.")
                else:
                    mask_to_color = binary_mask

                if color:
                    rgba[mask_to_color, 0] = color[0]
                    rgba[mask_to_color, 1] = color[1]
                    rgba[mask_to_color, 2] = color[2]
                rgba[mask_to_color, 3] = alpha
            
            plt.imsave(target_png_path, rgba)
            print(f"  Enhanced overlay PNG created at {target_png_path}")
            return True
    except Exception as e:
        print(f"Error creating enhanced overlay PNG from {source_tiff_path}: {e}")
        import traceback
        traceback.print_exc()
        return False

# --- Main Combined Function ---
def create_combined_map():
    print("--- Initializing Combined Map Creation ---")

    # 1. Prepare Archaeological Data
    print("\n--- Loading Archaeological Data ---")
    arch_dataframes = []
    arch_datasets_config = [
        {"file": "mound_villages_acre.csv", "name": "Mound Villages",
         "utm_params": {"x_col": "UTM X (Easting)", "y_col": "UTM Y (Northing)", "zone": 19}},
        {"file": "casarabe_sites_utm.csv", "name": "Casarabe Sites",
         "utm_params": {"x_col": "UTM X (Easting)", "y_col": "UTM Y (Northing)", "zone": 20}},
        {"file": "amazon_geoglyphs_sites.csv", "name": "Amazon Geoglyphs", "lat_col":"latitude", "lon_col":"longitude"},
        {"file": "submit.csv", "name": "Archaeological Survey Data", "extra_processing": process_submit_data},
        {"file": "science.ade2541_data_s2.csv", "name": "Science Data", "lat_col":"Latitude", "lon_col":"Longitude"}
    ]

    for config in arch_datasets_config:
        filepath = os.path.join(ARCHAEOLOGICAL_DATA_FOLDER, config["file"])
        df = read_arch_data(filepath, config["name"],
                            utm_conversion_params=config.get("utm_params"),
                            lat_col=config.get("lat_col", 'latitude'),
                            lon_col=config.get("lon_col", 'longitude'),
                            extra_processing_func=config.get("extra_processing"))
        if not df.empty:
            if config["name"] == "Amazon Geoglyphs" and len(df) > 2000:
                df = df.sample(n=2000, random_state=42)
                print(f"    Sampled Amazon Geoglyphs to {len(df)} sites.")
            elif config["name"] == "Archaeological Survey Data" and len(df) > 1000:
                df = df.sample(n=1000, random_state=42)
                print(f"    Sampled Archaeological Survey Data to {len(df)} sites.")
            arch_dataframes.append((config["name"], df))

    # 2. Prepare Raster Overlay
    print("\n--- Preparing Raster Overlay ---")
    overlay_filename_lower = os.path.basename(OVERLAY_SOURCE_TIFF_PATH).lower()
    if 'interfluves' in overlay_filename_lower or 'streams' in overlay_filename_lower:
        current_overlay_color = OVERLAY_COLOR_BINARY
        current_overlay_alpha = OVERLAY_ALPHA_BINARY
        current_dilation = DILATION_AMOUNT_BINARY
        overlay_type_name = "Binary Features (Interfluves/Streams)" # More specific name
    elif 'tpi' in overlay_filename_lower:
        current_overlay_color = None
        current_overlay_alpha = TPI_ALPHA
        current_dilation = 0
        overlay_type_name = "TPI"
    else:
        current_overlay_color = (0, 255, 255)
        current_overlay_alpha = 200
        current_dilation = DILATION_AMOUNT_BINARY
        overlay_type_name = "Generic Overlay"
    
    print(f"  Overlay Type: {overlay_type_name}, Dilation: {current_dilation}, Alpha: {current_overlay_alpha}")

    if not create_enhanced_overlay_png(
        OVERLAY_SOURCE_TIFF_PATH,
        TEMP_OVERLAY_PNG_PATH,
        color=current_overlay_color,
        alpha=current_overlay_alpha,
        dilation_iterations=current_dilation
        # nodata_val is handled inside create_enhanced_overlay_png based on type
    ):
        print("ERROR: Failed to create raster overlay PNG. Overlay will be skipped.")
        raster_overlay_available = False
    else:
        raster_overlay_available = True

    map_fit_bounds = get_raster_bounds(REFERENCE_BOUNDS_TIFF_PATH)
    overlay_placement_bounds = get_raster_bounds(OVERLAY_SOURCE_TIFF_PATH) if raster_overlay_available else None

    # 3. Create Folium Map
    print("\n--- Creating Folium Map ---")
    google_satellite_tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
    google_attribution = "Google Satellite"
    
    if map_fit_bounds:
        m = folium.Map(tiles=None)
        folium.TileLayer(tiles=google_satellite_tiles, attr=google_attribution, name="Google Satellite", overlay=False, control=True).add_to(m)
        m.fit_bounds(map_fit_bounds)
        print(f"  Map initially fitted to bounds of {os.path.basename(REFERENCE_BOUNDS_TIFF_PATH)}")
    else:
        m = folium.Map(location=MAP_CENTER_ARCH, zoom_start=MAP_ZOOM_ARCH, tiles=None)
        folium.TileLayer(tiles=google_satellite_tiles, attr=google_attribution, name="Google Satellite", overlay=False, control=True).add_to(m)
        print(f"  Map initially centered at {MAP_CENTER_ARCH}, zoom {MAP_ZOOM_ARCH} (reference raster bounds failed).")

    folium.TileLayer(
        tiles='OpenStreetMap',
        attr='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        name='OpenStreetMap',
        overlay=False, control=True
    ).add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles © Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
        name='Esri World Imagery', overlay=False, control=True
    ).add_to(m)
    folium.TileLayer(
        tiles='Stamen Terrain',
        attr='Map tiles by <a href="http://stamen.com">Stamen Design</a>, <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a> — Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        name='Stamen Terrain',
        overlay=False, control=True
    ).add_to(m)

    # 4. Add Archaeological Sites to Map
    print("\n--- Adding Archaeological Sites ---")
    arch_colors = {
        'Mound Villages': 'red', 'Casarabe Sites': 'blue',
        'Amazon Geoglyphs': 'orange', 'Archaeological Survey Data': 'green',
        'Science Data': 'purple'
    }
    arch_feature_groups = {}
    total_arch_points_plotted = 0

    for source_name, df in arch_dataframes:
        if source_name not in arch_feature_groups:
            arch_feature_groups[source_name] = folium.FeatureGroup(name=f"Sites: {source_name}", show=True)
        
        color = arch_colors.get(source_name, 'gray')
        valid_df = df.dropna(subset=['latitude', 'longitude'])
        
        if valid_df.empty:
            print(f"  No valid coordinates to plot for {source_name}.")
            continue

        print(f"  Plotting {len(valid_df)} sites for {source_name} (color: {color})")
        for _, row in valid_df.iterrows():
            popup_html = f"<b>Source:</b> {source_name}<br>"
            site_name_keys = ['Site Name', 'Site', 'name']
            for key in site_name_keys:
                if key in row and pd.notna(row[key]):
                    popup_html += f"<b>Site:</b> {row[key]}<br>"
                    break
            popup_html += f"<b>Coordinates:</b> {row['latitude']:.5f}, {row['longitude']:.5f}"
            
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=4,
                popup=folium.Popup(popup_html, max_width=300),
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                tooltip=f"{source_name}: {row.get(site_name_keys[0], 'Unknown Site')}"
            ).add_to(arch_feature_groups[source_name])
            total_arch_points_plotted +=1
        
        arch_feature_groups[source_name].add_to(m)
    print(f"  Total archaeological sites plotted: {total_arch_points_plotted}")

    # 5. Add Raster Overlay to Map
    if raster_overlay_available and overlay_placement_bounds and os.path.exists(TEMP_OVERLAY_PNG_PATH):
        print("\n--- Adding Raster Overlay to Map ---")
        img_overlay_name = f"Raster: {os.path.basename(OVERLAY_SOURCE_TIFF_PATH)} ({overlay_type_name})"
        img_overlay = folium.raster_layers.ImageOverlay(
            name=img_overlay_name,
            image=TEMP_OVERLAY_PNG_PATH,
            bounds=overlay_placement_bounds,
            opacity=1.0,
            interactive=True,
            cross_origin=False,
            show=True
        )
        raster_fg = folium.FeatureGroup(name="Raster Overlays", show=True) # Group for raster layers
        img_overlay.add_to(raster_fg)
        raster_fg.add_to(m)
        print(f"  Added '{img_overlay_name}' to the map.")
    else:
        print("\nSkipping raster overlay due to earlier errors or missing files.")
        
    # --- Define and Add Your Target AOI for GEDI Analysis (from your interfluves script) ---
    # ** MODIFY THESE COORDINATES based on your visual guess from the map **
    aoi_gedi_bounds_sw_ne = [ # These are [south_lat, west_lon], [north_lat, east_lon]
        [-12.85, -62.95],  # Approx South-West corner (latitude, longitude)
        [-12.70, -62.80]   # Approx North-East corner (latitude, longitude)
    ]
    # Ensure lats are south < north and lons are west < east if defining by SW/NE
    # Or, more robustly for folium.Rectangle, provide [[min_lat, min_lon], [max_lat, max_lon]]
    min_lat_aoi = min(aoi_gedi_bounds_sw_ne[0][0], aoi_gedi_bounds_sw_ne[1][0])
    max_lat_aoi = max(aoi_gedi_bounds_sw_ne[0][0], aoi_gedi_bounds_sw_ne[1][0])
    min_lon_aoi = min(aoi_gedi_bounds_sw_ne[0][1], aoi_gedi_bounds_sw_ne[1][1])
    max_lon_aoi = max(aoi_gedi_bounds_sw_ne[0][1], aoi_gedi_bounds_sw_ne[1][1])
    
    folium_aoi_for_rectangle = [[min_lat_aoi, min_lon_aoi], [max_lat_aoi, max_lon_aoi]]

    folium.Rectangle(
        bounds=folium_aoi_for_rectangle,
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.2,
        tooltip="Target AOI for GEDI Analysis"
    ).add_to(m)
    print(f"\nAdded Target AOI for GEDI Analysis at bounds: {folium_aoi_for_rectangle}")

    # 6. Add Map Controls and Save
    print("\n--- Finalizing Map ---")
    folium.LayerControl(collapsed=False).add_to(m)
    plugins.MiniMap(toggle_display=True, position="bottomright").add_to(m)
    plugins.MeasureControl(position='bottomleft', primary_length_unit='kilometers').add_to(m)
    plugins.Fullscreen(position="topright", force_separate_button=True).add_to(m)

    m.save(OUTPUT_HTML_MAP)
    print(f"Combined map saved to: {OUTPUT_HTML_MAP}")

    # 8. Cleanup temporary PNG
    if os.path.exists(TEMP_OVERLAY_PNG_PATH):
        try:
            # os.remove(TEMP_OVERLAY_PNG_PATH) # Uncomment to remove temp file
            print(f"  Temporary overlay PNG kept at {TEMP_OVERLAY_PNG_PATH} for inspection.")
        except Exception as e:
            print(f"  Warning: Could not remove temporary PNG {TEMP_OVERLAY_PNG_PATH}: {e}")

    print("\n--- Combined Map Script Finished ---")

# --- Main Execution Guard ---
if __name__ == "__main__":
    create_combined_map()