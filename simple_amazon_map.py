import folium

# Coordinates for São Francisco do Guaporé (Corrected Decimal Degrees)
# Original: -12° 03' 4.80" S, -63° 34' 1.79" W
sao_francisco_coords = [-12.051333, -63.567164]
sao_francisco_name = "São Francisco do Guaporé"

# 1. Define the centers for the three areas (still needed to calculate the map center)
area_centers_for_avg = [
    [-12.50, -63.30], # Area 1 center
    [-11.70, -63.00], # Area 2 center
    [-12.15, -63.38]  # Area 3 center
]

# 2. Determine a map center and initial zoom level
all_centers_for_avg = area_centers_for_avg + [sao_francisco_coords]
map_center_lat = sum(coords[0] for coords in all_centers_for_avg) / len(all_centers_for_avg)
map_center_lon = sum(coords[1] for coords in all_centers_for_avg) / len(all_centers_for_avg)
initial_map_center = [map_center_lat, map_center_lon]
initial_zoom = 9

# 3. Create a folium.Map object
google_satellite_tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
google_attribution = "Google Satellite"

m_clean = folium.Map(
    location=initial_map_center,
    zoom_start=initial_zoom,
    tiles=google_satellite_tiles,
    attr=google_attribution
)

# Add marker for São Francisco do Guaporé
folium.Marker(
    location=sao_francisco_coords,
    tooltip=sao_francisco_name,
    popup=f"<b>{sao_francisco_name}</b><br>Coords: {sao_francisco_coords[0]:.6f}, {sao_francisco_coords[1]:.6f}",
    icon=folium.Icon(color='orange', icon='info-sign') # Orange marker
).add_to(m_clean)

# 5. Save the map to a new HTML file
output_filename_clean = "amazon_research_areas_map_clean_with_town_corrected.html"
m_clean.save(output_filename_clean)

print(f"Clean map with corrected town saved to {output_filename_clean}")