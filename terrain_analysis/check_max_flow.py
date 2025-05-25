import rasterio
import numpy as np
import os

facc_path = "output_data/intermediate_outputs/facc_wbt.tif"

if os.path.exists(facc_path):
    with rasterio.open(facc_path) as src:
        facc_data = src.read(1)
        nodata = src.nodatavals[0] if src.nodatavals else None
        if nodata is not None:
            facc_data = facc_data[facc_data != nodata] # Exclude nodata for min/max
        if facc_data.size > 0:
            print(f"Flow Accumulation Min: {np.min(facc_data)}")
            print(f"Flow Accumulation Max: {np.max(facc_data)}")
            print(f"Flow Accumulation Mean: {np.mean(facc_data)}")
            print(f"Flow Accumulation Median: {np.median(facc_data)}")
            print(f"Flow Accumulation 95th percentile: {np.percentile(facc_data, 95)}")
            print(f"Flow Accumulation 99th percentile: {np.percentile(facc_data, 99)}")
        else:
            print("No valid data in FACC raster after excluding nodata.")
else:
    print(f"FACC file not found: {facc_path}")
