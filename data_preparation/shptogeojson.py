import geopandas
import os

# --- Configuration ---
shapefile_path = "input_data/ne_10m_admin_0_countries.shp"
output_geojson_path = "input_data/ne_10m_admin_0_countries.geojson"
# Ensure output directory for GeoJSON exists if it's different from input
# os.makedirs(os.path.dirname(output_geojson_path), exist_ok=True) # Not strictly needed if saving to same dir as input_data

if __name__ == "__main__":
    if not os.path.exists(shapefile_path):
        print(f"ERROR: Shapefile not found at: {shapefile_path}")
    else:
        try:
            # Read the shapefile
            gdf = geopandas.read_file(shapefile_path)

            # Check if CRS is already WGS84, if not, reproject
            # Natural Earth data is typically already in EPSG:4326 (WGS84)
            if gdf.crs is None:
                print("Warning: Input shapefile has no CRS defined. Assuming WGS84 (EPSG:4326).")
                # If you know for sure it's WGS84, you could assign it:
                # gdf = gdf.set_crs("EPSG:4326", allow_override=True)
            elif gdf.crs.to_epsg() != 4326:
                print(f"Reprojecting from {gdf.crs} to EPSG:4326 (WGS84)...")
                gdf = gdf.to_crs("EPSG:4326") # Reproject to WGS84 if it's not already

            # Save to GeoJSON
            # When saving to GeoJSON, geopandas should default to WGS84 if the gdf is in WGS84
            gdf.to_file(output_geojson_path, driver="GeoJSON")
            print(f"Successfully converted Shapefile to GeoJSON: {output_geojson_path}")
            print("You can now use this GeoJSON file in your Folium script.")
        except Exception as e:
            print(f"An error occurred during conversion: {e}")
