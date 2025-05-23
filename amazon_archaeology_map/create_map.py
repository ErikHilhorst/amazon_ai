"""
Archaeological Sites Visualization Script
==========================================

This script reads archaeological site data from multiple files and creates
interactive maps showing the locations of various archaeological sites in
the Amazon region.

Requirements:
- pandas
- numpy
- folium
- pyproj (for coordinate transformations)
- openpyxl (for Excel files)

Install with: pip install pandas numpy folium pyproj openpyxl
"""

import pandas as pd
import numpy as np
import folium
from folium import plugins
# import re # 're' was imported but not used in the original script, can be removed or kept
from pyproj import Transformer
# import openpyxl # openpyxl is a dependency for pandas reading .xlsx, not directly used here for .csv
# from IPython.display import display # Not needed for local script execution

# Configuration
MAP_CENTER = [-10.0, -67.0]  # Approximate center of Amazon region
MAP_ZOOM = 3

def utm_to_latlon(utm_x, utm_y, utm_zone=19, hemisphere='south'):
    """
    Convert UTM coordinates to latitude/longitude.

    Parameters:
    utm_x, utm_y: UTM coordinates
    utm_zone: UTM zone (default 19 for western Brazil)
    hemisphere: 'north' or 'south'
    """
    # from pyproj import Transformer # Already imported at the top

    # Define the coordinate systems
    # For EPSG codes: 326XX for UTM North, 327XX for UTM South
    # XX is the zone number.
    utm_crs_code = 32600 + utm_zone if hemisphere == 'north' else 32700 + utm_zone
    utm_crs = f"EPSG:{utm_crs_code}"
    wgs84_crs = "EPSG:4326" # Standard Latitude/Longitude

    # Create transformer
    transformer = Transformer.from_crs(utm_crs, wgs84_crs, always_xy=True)

    # Transform coordinates (returns lon, lat)
    lon, lat = transformer.transform(utm_x, utm_y)
    return lat, lon

def read_mound_villages_data(filepath):
    """
    Read the mound villages data from CSV file.
    """
    try:
        df = pd.read_csv(filepath)

        # Convert UTM to lat/lon (using UTM zone 19S as indicated in original data)
        lats, lons = [], []
        for _, row in df.iterrows():
            if pd.notna(row['UTM X (Easting)']) and pd.notna(row['UTM Y (Northing)']):
                lat, lon = utm_to_latlon(row['UTM X (Easting)'], row['UTM Y (Northing)'], utm_zone=19, hemisphere='south')
                lats.append(lat)
                lons.append(lon)
            else:
                lats.append(np.nan)
                lons.append(np.nan)

        df['latitude'] = lats
        df['longitude'] = lons
        df['source'] = 'Mound Villages'

        return df

    except FileNotFoundError:
        print(f"Error: File not found at {filepath}. Skipping mound villages data.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading mound villages data from {filepath}: {e}")
        return pd.DataFrame()

def read_casarabe_sites_data(filepath):
    """
    Read the Casarabe sites data from CSV file.
    """
    try:
        df = pd.read_csv(filepath)

        # Convert UTM to lat/lon
        lats, lons = [], []
        for _, row in df.iterrows():
            if pd.notna(row['UTM X (Easting)']) and pd.notna(row['UTM Y (Northing)']):
                # Assuming UTM zone 20S for Casarabe sites (Bolivia region)
                lat, lon = utm_to_latlon(row['UTM X (Easting)'], row['UTM Y (Northing)'], utm_zone=20, hemisphere='south')
                lats.append(lat)
                lons.append(lon)
            else:
                lats.append(np.nan)
                lons.append(np.nan)

        df['latitude'] = lats
        df['longitude'] = lons
        df['source'] = 'Casarabe Sites'

        return df

    except FileNotFoundError:
        print(f"Error: File not found at {filepath}. Skipping Casarabe sites data.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading Casarabe sites data from {filepath}: {e}")
        return pd.DataFrame()

def read_geoglyphs_data(filepath):
    """
    Read the Amazon geoglyphs data from CSV file.
    """
    try:
        df = pd.read_csv(filepath)

        # Convert latitude to numeric (it might be a string)
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

        df['source'] = 'Amazon Geoglyphs'

        return df

    except FileNotFoundError:
        print(f"Error: File not found at {filepath}. Skipping geoglyphs data.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading geoglyphs data from {filepath}: {e}")
        return pd.DataFrame()

def read_submit_data(filepath):
    """
    Read the submit.csv data.
    This file was originally from a dataset named 'archaeological-survey-data'.
    """
    try:
        df = pd.read_csv(filepath)

        # Check if coordinates are already in lat/lon format
        sample_x = df['x'].iloc[0] if len(df) > 0 and 'x' in df.columns else None
        sample_y = df['y'].iloc[0] if len(df) > 0 and 'y' in df.columns else None

        # Heuristic to check if data is already lat/lon
        is_lat_lon = False
        if sample_x is not None and sample_y is not None:
            if isinstance(sample_x, (int, float)) and isinstance(sample_y, (int, float)):
                 if -180 <= sample_x <= 180 and -90 <= sample_y <= 90:
                    is_lat_lon = True

        if is_lat_lon:
            df['latitude'] = df['y']
            df['longitude'] = df['x']
        elif 'x' in df.columns and 'y' in df.columns: # Ensure x and y columns exist for UTM conversion
            # Coordinates might be in UTM, convert them
            df['latitude'] = np.nan
            df['longitude'] = np.nan

            # Try to determine appropriate UTM zone based on coordinate ranges
            for idx, row in df.iterrows():
                if pd.notna(row['x']) and pd.notna(row['y']):
                    try:
                        # Try different UTM zones (18-22 are common for Amazon region, assuming South)
                        for zone in [18, 19, 20, 21, 22]:
                            try:
                                lat, lon = utm_to_latlon(row['x'], row['y'], utm_zone=zone, hemisphere='south')
                                # Check if the converted coordinates are valid lat/lon
                                if -90 <= lat <= 90 and -180 <= lon <= 180:
                                    df.at[idx, 'latitude'] = lat
                                    df.at[idx, 'longitude'] = lon
                                    break # Found a valid conversion
                            except Exception: # pyproj might raise error if coords are way out of zone
                                continue
                    except Exception: # General error handling for the row
                        continue
        else:
            print(f"Warning: 'x' or 'y' columns not found in {filepath} for coordinate conversion. Skipping coordinate processing for this file.")
            df['latitude'] = np.nan
            df['longitude'] = np.nan


        df['source'] = 'Archaeological Survey Data'

        return df

    except FileNotFoundError:
        print(f"Error: File not found at {filepath}. Skipping submit data.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading submit data from {filepath}: {e}")
        return pd.DataFrame()

def read_science_data(filepath):
    """
    Read the science data from CSV file.
    This file was originally 'science.ade2541_data_s2.csv'.
    """
    try:
        df = pd.read_csv(filepath)

        # The data already has Latitude and Longitude columns
        df['latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

        df['source'] = 'Science Data'

        return df

    except FileNotFoundError:
        print(f"Error: File not found at {filepath}. Skipping science data.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading science data from {filepath}: {e}")
        return pd.DataFrame()

def create_map(dataframes_list):
    """
    Create an interactive map with all archaeological sites.
    """
    # Create base map
    m = folium.Map(
        location=MAP_CENTER,
        zoom_start=MAP_ZOOM,
        tiles='OpenStreetMap' # Default base layer
    )

    # Add different tile layers with proper attributions
    folium.TileLayer(
        tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', # Standard OpenStreetMap
        attr='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        name='OpenStreetMap',
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles © Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
        name='Esri World Imagery',
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles='https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}{r}.png',
        attr='Map tiles by <a href="http://stamen.com">Stamen Design</a>, <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a> — Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        name='Stamen Terrain',
        overlay=False,
        control=True
    ).add_to(m)

    # Color mapping for different sources
    colors = {
        'Mound Villages': 'red',
        'Casarabe Sites': 'blue',
        'Amazon Geoglyphs': 'orange',
        'Archaeological Survey Data': 'green',
        'Science Data': 'purple'
    }

    # Create feature groups for different data sources
    feature_groups = {}
    for source_name in colors.keys(): # Iterate over defined sources to ensure all groups are created
        feature_groups[source_name] = folium.FeatureGroup(name=source_name, show=True) # Show by default

    # Add points for each dataset
    total_points_added = 0
    for df_source_name, df in dataframes_list: # df_source_name is like 'Mound Villages'
        if df.empty:
            print(f"  - No data for {df_source_name}, skipping.")
            continue

        # Ensure the source name from the dataframe matches one of our defined feature groups/colors
        # This loop assumes df['source'].iloc[0] is consistent for the whole dataframe
        # and matches one of the keys in 'colors' and 'feature_groups'.
        # This might not always be robust if df['source'] is missing or inconsistent.
        # Using df_source_name passed in dataframes_list is more reliable here.
        source_color = colors.get(df_source_name, 'black') # Default to black if source name not in colors
        current_feature_group = feature_groups.get(df_source_name)

        if not current_feature_group:
            print(f"Warning: No feature group defined for source '{df_source_name}'. Points might not be added correctly.")
            continue # Skip if no feature group

        # Filter valid coordinates
        valid_coords_df = df.dropna(subset=['latitude', 'longitude'])
        print(f"  - Processing {len(valid_coords_df)} sites for {df_source_name} (color: {source_color})")


        for idx, row in valid_coords_df.iterrows():
            # Create popup text
            popup_html = f"<b>Source:</b> {df_source_name}<br>"

            # Site name handling
            site_name_keys = ['Site Name', 'Site', 'name']
            for key in site_name_keys:
                if key in row and pd.notna(row[key]):
                    popup_html += f"<b>Site:</b> {row[key]}<br>"
                    break

            # Classification and type information
            type_keys = ['Classification', 'PlotType', 'type']
            for key in type_keys:
                if key in row and pd.notna(row[key]):
                    popup_html += f"<b>Type:</b> {row[key]}<br>"
                    break
            
            # Location information
            if 'Country' in row and pd.notna(row['Country']):
                popup_html += f"<b>Country:</b> {row['Country']}<br>"
            if 'Subdivision' in row and pd.notna(row['Subdivision']):
                popup_html += f"<b>Region:</b> {row['Subdivision']}<br>"

            # Numerical data
            numerical_info = {
                'Number of mounds': 'Mounds',
                'Diameter (m)': 'Diameter (m)',
                'Elevation (m)': 'Elevation (m)',
                'Altitude': 'Altitude (m)', # Assuming Altitude is in meters
                'PlotSize': 'Plot Size'
            }
            for col, label in numerical_info.items():
                if col in row and pd.notna(row[col]):
                    try: # Attempt to format as int if it's a whole number, else as float
                        val = float(row[col])
                        if val == int(val):
                            popup_html += f"<b>{label}:</b> {int(val)}<br>"
                        else:
                            popup_html += f"<b>{label}:</b> {val:.2f}<br>"
                    except ValueError:
                         popup_html += f"<b>{label}:</b> {row[col]}<br>"


            # Additional features
            if 'LIDAR' in row and pd.notna(row['LIDAR']):
                popup_html += f"<b>LIDAR Coverage:</b> {row['LIDAR']}<br>"
            if 'Associated features' in row and pd.notna(row['Associated features']):
                popup_html += f"<b>Features:</b> {row['Associated features']}<br>"

            popup_html += f"<b>Coordinates:</b> {row['latitude']:.6f}, {row['longitude']:.6f}"

            # Add marker
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=5,
                popup=folium.Popup(popup_html, max_width=350),
                color=source_color,
                fill=True,
                fill_color=source_color,
                fill_opacity=0.7,
                tooltip=f"{df_source_name}: {row.get('Site Name', row.get('Site', row.get('name', 'Unknown Site')))}" # Tooltip for hover
            ).add_to(current_feature_group)

            total_points_added += 1

    # Add feature groups to map
    for fg_name, fg_object in feature_groups.items():
        fg_object.add_to(m)
        print(f"  - Added FeatureGroup: {fg_name}")

    # Add layer control
    folium.LayerControl(collapsed=False).add_to(m)

    # Add minimap
    minimap = plugins.MiniMap(toggle_display=True, position="bottomright")
    m.add_child(minimap)

    # Add measure control
    plugins.MeasureControl(
        position='bottomleft',
        primary_length_unit='kilometers',
        secondary_length_unit='miles',
        primary_area_unit='sqkilometers',
        secondary_area_unit='acres'
    ).add_to(m)

    # Add fullscreen button
    plugins.Fullscreen(
        position="topright",
        title="Fullscreen",
        title_cancel="Exit Fullscreen",
        force_separate_button=True
    ).add_to(m)

    # Add LatLng Popover
  #  folium.plugins.LatLngPopup().add_to(m)

    # Add Draw plugin
    # draw = plugins.Draw(
    #     export=True,
    #     filename='drawn_features.geojson',
    #     position='topleft',
    #     draw_options={'polyline': True, 'polygon': True, 'circle': False, 'marker': True, 'circlemarker': False},
    #     edit_options={'featureGroup': None} # Drawing on the map directly
    # )
    # draw.add_to(m)


    print(f"\nCreated map with {total_points_added} archaeological sites from all sources.")
    return m

def main():
    """
    Main function to read all data and create the map.
    """
    print("Starting archaeological site data processing...")

    dataframes = [] # List to hold tuples of (source_name, dataframe)

    # Define file paths - assuming CSVs are directly in a 'data' subfolder
    data_folder = "data" # Define the subfolder name

    # 1. Read mound villages data
    print("\nReading mound villages data...")
    mound_file = f"{data_folder}/mound_villages_acre.csv"
    mound_df = read_mound_villages_data(mound_file)
    if not mound_df.empty:
        dataframes.append(('Mound Villages', mound_df))
        print(f"  - Loaded {len(mound_df)} records from {mound_file}. Valid coordinates: {len(mound_df.dropna(subset=['latitude', 'longitude']))}")

    # 2. Read Casarabe sites
    print("\nReading Casarabe sites...")
    casarabe_file = f"{data_folder}/casarabe_sites_utm.csv"
    casarabe_df = read_casarabe_sites_data(casarabe_file)
    if not casarabe_df.empty:
        dataframes.append(('Casarabe Sites', casarabe_df))
        print(f"  - Loaded {len(casarabe_df)} records from {casarabe_file}. Valid coordinates: {len(casarabe_df.dropna(subset=['latitude', 'longitude']))}")

    # 3. Read Amazon geoglyphs
    print("\nReading Amazon geoglyphs...")
    geoglyphs_file = f"{data_folder}/amazon_geoglyphs_sites.csv"
    geoglyphs_df = read_geoglyphs_data(geoglyphs_file)
    if not geoglyphs_df.empty:
        original_count = len(geoglyphs_df)
        # Sample if too large for performance (adjust N as needed)
        if original_count > 2000:
            geoglyphs_df = geoglyphs_df.sample(n=2000, random_state=42)
            print(f"  - Sampled 2000 geoglyphs from {original_count} total for performance.")
        dataframes.append(('Amazon Geoglyphs', geoglyphs_df))
        print(f"  - Loaded {len(geoglyphs_df)} records from {geoglyphs_file}. Valid coordinates: {len(geoglyphs_df.dropna(subset=['latitude', 'longitude']))}")

    # 4. Read submit data (from archaeological-survey-data)
    print("\nReading submit data (Archaeological Survey Data)...")
    submit_file = f"{data_folder}/submit.csv" # This is the file originally from 'archaeological-survey-data'
    submit_df = read_submit_data(submit_file)
    if not submit_df.empty:
        original_count = len(submit_df)
        # Sample if too large
        if original_count > 1000:
            submit_df = submit_df.sample(n=1000, random_state=42)
            print(f"  - Sampled 1000 points from {original_count} total for performance.")
        dataframes.append(('Archaeological Survey Data', submit_df))
        print(f"  - Loaded {len(submit_df)} records from {submit_file}. Valid coordinates: {len(submit_df.dropna(subset=['latitude', 'longitude']))}")

    # 5. Read science data
    print("\nReading science data...")
    science_file = f"{data_folder}/science.ade2541_data_s2.csv" # This is the file originally from 'science-data'
    science_df = read_science_data(science_file)
    if not science_df.empty:
        dataframes.append(('Science Data', science_df))
        print(f"  - Loaded {len(science_df)} records from {science_file}. Valid coordinates: {len(science_df.dropna(subset=['latitude', 'longitude']))}")

    if not dataframes:
        print("\nNo data loaded. Exiting map creation.")
        return None

    # Create the map
    print("\nCreating interactive map...")
    map_obj = create_map(dataframes)

    if map_obj:
        # Save the map
        output_filename = 'archaeological_sites_map.html'
        map_obj.save(output_filename)
        print(f"\nMap saved as '{output_filename}'")
        print("Open this file in a web browser to view the interactive map.")

        # Display basic statistics
        print("\n=== Summary of Plotted Data ===")
        total_sites_plotted = 0
        for name, df in dataframes:
            valid_coords_count = len(df.dropna(subset=['latitude', 'longitude']))
            print(f"  - {name}: {valid_coords_count} sites with valid coordinates plotted.")
            total_sites_plotted += valid_coords_count
        print(f"Total archaeological sites plotted on map: {total_sites_plotted}")
    else:
        print("\nMap object was not created (likely due to no data).")

    return map_obj

# --- Main execution ---
if __name__ == "__main__":
    # Run the main visualization
    map_object = main()

    # The 'display(map_object)' line is for Jupyter/IPython environments.
    # For a local script, saving to HTML is the primary output.
    # If you are running this in an environment that supports IPython display, you can uncomment it.
    # For example, if running in a VS Code Jupyter notebook cell.
    # if map_object and 'IPython' in sys.modules:
    #     from IPython.display import display
    #     print("\nAttempting to display map inline (if in a suitable environment)...")
    #     display(map_object)

    print("\nVisualization script complete!")