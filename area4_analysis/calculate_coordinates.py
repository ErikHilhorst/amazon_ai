import math

center_lat = -12.8
center_lon = -62.875
box_side_km = 20.0 # The total side length of the square box

# Half the side length, as we're calculating +/- from the center
half_side_km = box_side_km / 2.0

# More precise degrees per km estimates
# Earth's radius in km (approximate mean radius)
R_earth_km = 6371.0

# Change in latitude for a given distance North/South
# d_lat = (distance_km / R_earth_km) * (180 / math.pi)
delta_lat_degrees = (half_side_km / R_earth_km) * (180.0 / math.pi)

# Change in longitude for a given distance East/West
# d_lon = (distance_km / (R_earth_km * cos(lat_radians))) * (180 / math.pi)
center_lat_rad = math.radians(center_lat)
delta_lon_degrees = (half_side_km / (R_earth_km * math.cos(center_lat_rad))) * (180.0 / math.pi)

lat_sw = center_lat - delta_lat_degrees
lon_sw = center_lon - delta_lon_degrees
lat_ne = center_lat + delta_lat_degrees
lon_ne = center_lon + delta_lon_degrees

# Rounding for practical use, e.g., 5 decimal places
bounding_box = [
    round(lat_sw, 5),
    round(lon_sw, 5),
    round(lat_ne, 5),
    round(lon_ne, 5)
]

print(f"Center: [{center_lat}, {center_lon}]")
print(f"Box Side: {box_side_km} km")
print(f"Delta Lat (degrees): {delta_lat_degrees:.5f}")
print(f"Delta Lon (degrees): {delta_lon_degrees:.5f}")
print(f"Calculated Bounding Box [lat_sw, lon_sw, lat_ne, lon_ne]:")
print(bounding_box)

# Verify the span
lat_span_deg = lat_ne - lat_sw
lon_span_deg = lon_ne - lon_sw

lat_span_km = lat_span_deg * (math.pi / 180.0) * R_earth_km
lon_span_km = lon_span_deg * (math.pi / 180.0) * (R_earth_km * math.cos(center_lat_rad))

print(f"Resulting box latitude span: {lat_span_km:.2f} km")
print(f"Resulting box longitude span: {lon_span_km:.2f} km")