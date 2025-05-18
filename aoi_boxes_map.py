import folium
import os
import numpy as np # For calculating centroid if needed

# --- Configuration ---
project_base_dir = os.path.dirname(os.path.abspath(__file__)) # Assumes script is in project base
output_images_dir = os.path.join(project_base_dir, 'output_images_aoi_bounds')
os.makedirs(output_images_dir, exist_ok=True)
output_html_map = os.path.join(output_images_dir, "aoi_with_borders_map.html")

# Your AOI coordinates
# Original format: [[lon, lat], [lon, lat], ...]
# Folium needs [[lat, lon], [lat, lon], ...] for polygons and fitting bounds
aoi_coordinates_lon_lat = [
    [-63.8, -13.0],  # Bottom-left (lon, lat)
    [-62.8, -13.0],  # Bottom-right
    [-62.8, -12.0],  # Top-right
    [-63.8, -12.0],  # Top-left
    [-63.8, -13.0]   # Close polygon (optional for simple rectangle, good for polygon)
]

# Convert to [[lat, lon]] for Folium
aoi_bounds_folium_format = [[coord[1], coord[0]] for coord in aoi_coordinates_lon_lat]

# --- Calculate Center and Bounds for Folium ---
# For a simple rectangle defined by min/max lat/lon:
min_lon = min(coord[0] for coord in aoi_coordinates_lon_lat)
max_lon = max(coord[0] for coord in aoi_coordinates_lon_lat)
min_lat = min(coord[1] for coord in aoi_coordinates_lon_lat)
max_lat = max(coord[1] for coord in aoi_coordinates_lon_lat)

# Bounds for m.fit_bounds() in [[south_lat, west_lon], [north_lat, east_lon]]
map_fit_bounds = [[min_lat, min_lon], [max_lat, max_lon]]

# Calculate approximate center for map initialization (optional, as fit_bounds will adjust)
center_lat = (min_lat + max_lat) / 2
center_lon = (min_lon + max_lon) / 2

# --- Main Script ---
if __name__ == "__main__":
    print(f"AOI Min/Max Lat: {min_lat}, {max_lat}")
    print(f"AOI Min/Max Lon: {min_lon}, {max_lon}")
    print(f"Map will be centered around: Lat {center_lat}, Lon {center_lon}")
    print(f"Map will fit to bounds: {map_fit_bounds}")

    # Create a folium.Map object
    # Using OpenStreetMap by default as it clearly shows borders
    # You can also use Google Satellite as in your previous script:
    # tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google Satellite"
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=8, # Initial zoom, will be adjusted by fit_bounds
        tiles="OpenStreetMap", # Clearly shows country borders
        attr="OpenStreetMap"
    )

    # Add Google Satellite as an alternative layer if you prefer its visual style
    google_satellite_tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
    folium.TileLayer(
        tiles=google_satellite_tiles,
        attr='Google Satellite',
        name='Google Satellite',
        overlay=False, # Make it a base layer option, not an overlay
        control=True
    ).add_to(m)


    # Add your AOI as a red rectangle
    # The bounds for folium.Rectangle are [[south_lat, west_lon], [north_lat, east_lon]]
    folium.Rectangle(
        bounds=map_fit_bounds, # Uses the [[min_lat, min_lon], [max_lat, max_lon]] format
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.1, # Semi-transparent fill
        tooltip="Your Area of Interest (AOI)"
    ).add_to(m)

    # Fit map to the AOI's bounds
    m.fit_bounds(map_fit_bounds)

    # Add Layer Control to switch between OpenStreetMap and Satellite if desired
    folium.LayerControl().add_to(m)

    # Save the map to an HTML file
    m.save(output_html_map)
    print(f"Map with AOI box saved to {output_html_map}")
    print(f"Open this HTML file in a web browser to view the map.")