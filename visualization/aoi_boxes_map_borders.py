import folium
import os
import json # Still good to have for opening/inspecting GeoJSON if needed

# --- Configuration ---
output_html_map = "output_data/maps/aoi_with_simple_borders_map.html"
# Ensure the new output directory exists before saving, or handle in script
os.makedirs(os.path.dirname(output_html_map), exist_ok=True)

# Path to your GeoJSON file (which has empty properties)
country_borders_geojson_path = "input_data/ne_10m_admin_0_countries.geojson"

# Your AOI coordinates (lon, lat)
aoi_coordinates_lon_lat = [
    [-63.8, -13.0],
    [-62.8, -13.0],
    [-62.8, -12.0],
    [-63.8, -12.0],
    [-63.8, -13.0]
]

# --- Calculate Center and Bounds for Folium ---
min_lon = min(coord[0] for coord in aoi_coordinates_lon_lat)
max_lon = max(coord[0] for coord in aoi_coordinates_lon_lat)
min_lat = min(coord[1] for coord in aoi_coordinates_lon_lat)
max_lat = max(coord[1] for coord in aoi_coordinates_lon_lat)
map_fit_bounds = [[min_lat, min_lon], [max_lat, max_lon]]
center_lat = (min_lat + max_lat) / 2
center_lon = (min_lon + max_lon) / 2

# --- Main Script ---
if __name__ == "__main__":
    if not os.path.exists(country_borders_geojson_path):
        print(f"ERROR: Country borders GeoJSON file not found at: {country_borders_geojson_path}")
        exit()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=7,
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", # Default to Satellite
        attr="Google Satellite"
    )

    folium.TileLayer(
        tiles="OpenStreetMap",
        attr='OpenStreetMap',
        name='OpenStreetMap',
        overlay=False,
        control=True
    ).add_to(m)

    # --- Add Country Borders from GeoJSON (Simplified) ---
    try:
        def style_function(feature):
            return {
                'fillOpacity': 0,
                'weight': 1.5,
                'color': '#FFFF00' # Bright yellow
            }

        borders_overlay = folium.GeoJson(
            country_borders_geojson_path,
            name="Country Borders", # Simplified name
            style_function=style_function
            # NO TOOLTIP if properties are empty
        )
        borders_overlay.add_to(m)
        print("Country borders GeoJSON layer added.")

    except Exception as e:
        print(f"Could not load or add GeoJSON layer: {e}")

    folium.Rectangle(
        bounds=map_fit_bounds,
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.2,
        tooltip="Your Area of Interest (AOI)"
    ).add_to(m)

    m.fit_bounds(map_fit_bounds)
    folium.LayerControl().add_to(m)
    m.save(output_html_map)
    print(f"Map with AOI box and simple borders saved to {output_html_map}")
