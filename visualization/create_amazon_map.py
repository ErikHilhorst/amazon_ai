import folium

# Coordinates for São Francisco do Guaporé (Corrected Decimal Degrees)
# Original: -12° 03' 4.80" S, -63° 34' 1.79" W
sao_francisco_coords = [-12.051333, -63.567164]
sao_francisco_name = "São Francisco do Guaporé"

# 1. Define the coordinates for the three areas
areas_data = [
    {
        "name": "Area 1",
        "bounds": [[-12.59, -63.39], [-12.41, -63.21]],
        "center": [-12.50, -63.30],
        "color": "blue",
        "description": "Interfluve Guaporé/São Miguel, near BR-429"
    },
    {
        "name": "Area 2",
        "bounds": [[-11.79, -63.09], [-11.61, -62.91]],
        "center": [-11.70, -63.00],
        "color": "green",
        "description": "Interfluve São Miguel/Cautário, near Seringueiras"
    },
    {
        "name": "Area 3",
        "bounds": [[-12.24, -63.47], [-12.06, -63.29]],
        "center": [-12.15, -63.38],
        "color": "red",
        "description": "Headwaters east of São Francisco do Guaporé"
    }
]

# 2. Determine a map center and initial zoom level
all_centers_for_avg = [area["center"] for area in areas_data] + [sao_francisco_coords]
map_center_lat = sum(coords[0] for coords in all_centers_for_avg) / len(all_centers_for_avg)
map_center_lon = sum(coords[1] for coords in all_centers_for_avg) / len(all_centers_for_avg)
initial_map_center = [map_center_lat, map_center_lon]
initial_zoom = 9

# 3. Create a folium.Map object
google_satellite_tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
google_attribution = "Google Satellite"

m = folium.Map(
    location=initial_map_center,
    zoom_start=initial_zoom,
    tiles=google_satellite_tiles,
    attr=google_attribution
)

# 4. Add the rectangular areas and labels to the map
for area in areas_data:
    folium.Rectangle(
        bounds=area["bounds"],
        color=area["color"],
        fill=True,
        fill_color=area["color"],
        fill_opacity=0.2,
        tooltip=f"<b>{area['name']}</b><br>{area['description']}"
    ).add_to(m)

    folium.Marker(
        location=area["center"],
        tooltip=f"<b>{area['name']}</b>",
        icon=None # Default blue marker
    ).add_to(m)

# Add marker for São Francisco do Guaporé
folium.Marker(
    location=sao_francisco_coords,
    tooltip=sao_francisco_name,
    popup=f"<b>{sao_francisco_name}</b><br>Coords: {sao_francisco_coords[0]:.6f}, {sao_francisco_coords[1]:.6f}",
    icon=folium.Icon(color='orange', icon='info-sign') # Orange marker for distinction
).add_to(m)

import os # Add os import for makedirs
# 5. Save the map to an HTML file
output_filename = "output_data/maps/amazon_research_areas_map_with_town_corrected.html"
os.makedirs(os.path.dirname(output_filename), exist_ok=True)
m.save(output_filename)

print(f"Map with areas and corrected town saved to {output_filename}")
