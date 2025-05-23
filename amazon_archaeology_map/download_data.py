import kagglehub
from kagglehub import KaggleDatasetAdapter
import pandas as pd
import os

# --- Configuration ---
# This list defines:
# 1. The Kaggle slug to use (as provided by you).
# 2. The specific file to attempt to load from that dataset (based on visualization script needs).
# 3. The subfolder within 'data/' where this file should be saved.
# 4. The filename to use when saving locally.

datasets_to_process = [
    {
        "slug": "fafa92/mound-villages-acre",
        "file_to_load": "mound_villages_acre.csv", # Expected by read_mound_villages_data
        "local_folder_name": "mound-villages-acre",
        "local_filename": "mound_villages_acre.csv"
    },
    {
        "slug": "fafa92/casarabe-sites-utm",
        "file_to_load": "casarabe_sites_utm.csv",    # Expected by read_casarabe_sites_data
        "local_folder_name": "casarabe-sites-utm",
        "local_filename": "casarabe_sites_utm.csv"
    },
    {
        "slug": "fafa92/amazon-geoglyphs-sites",
        "file_to_load": "amazon_geoglyphs_sites.csv",# Expected by read_geoglyphs_data
        "local_folder_name": "amazon-geoglyphs-sites",
        "local_filename": "amazon_geoglyphs_sites.csv"
    },
    {
        "slug": "fafa92/archaeological-survey-data",
        "file_to_load": "submit.csv",                # Expected by read_submit_data
        "local_folder_name": "archaeological-survey-data",
        "local_filename": "submit.csv"
    },
    {
        "slug": "fafa92/science-data",
        "file_to_load": "science.ade2541_data_s2.csv", # Expected by read_science_data
        "local_folder_name": "science-data",
        "local_filename": "science.ade2541_data_s2.csv"
    },
    # The "fafa92/river-segments" slug was in your list.
    # The visualization script doesn't use it. If you need it for other purposes,
    # you'll need to know the exact CSV filename within that dataset.
    # Example (you'd need to replace 'actual_filename_in_dataset.csv'):
    # {
    #     "slug": "fafa92/river-segments",
    #     "file_to_load": "actual_filename_in_dataset.csv",
    #     "local_folder_name": "river-segments",
    #     "local_filename": "actual_filename_in_dataset.csv"
    # },
]

# Base download directory
base_data_dir = "data"

def main():
    if not os.path.exists(base_data_dir):
        os.makedirs(base_data_dir)
        print(f"Created base data directory: {base_data_dir}")

    print("--- Starting dataset loading and saving process ---")
    print("IMPORTANT: This script uses the slugs you provided.")
    print("If these slugs previously resulted in 404 (Not Found) errors, they will likely fail here too,")
    print("as the Kaggle API will be unable to find a dataset with that exact OWNER/DATASET_NAME.\n")

    for item in datasets_to_process:
        slug = item["slug"]
        file_to_load = item["file_to_load"]
        local_folder_name = item["local_folder_name"]
        local_filename = item["local_filename"]

        # Create the specific subdirectory for this dataset's file
        target_save_dir = os.path.join(base_data_dir, local_folder_name)
        if not os.path.exists(target_save_dir):
            os.makedirs(target_save_dir)
            print(f"Created subfolder: {target_save_dir}")

        full_local_path = os.path.join(target_save_dir, local_filename)

        print(f"\nAttempting to load: '{file_to_load}' from dataset '{slug}'")
        print(f"Target save path: '{full_local_path}'")

        try:
            # Load the specified file from the dataset directly into a pandas DataFrame
            df = kagglehub.load_dataset(
                KaggleDatasetAdapter.PANDAS,
                slug,
                file_path=file_to_load  # This tells kagglehub which file in the dataset to load
            )

            # Save the DataFrame to a CSV file locally
            df.to_csv(full_local_path, index=False)
            print(f"Successfully loaded and saved '{file_to_load}' to '{full_local_path}'")

        except Exception as e:
            print(f"ERROR processing dataset '{slug}' (file: '{file_to_load}'):")
            print(f"  {e}")
            print("  Possible reasons for failure:")
            print(f"    1. The Kaggle dataset slug '{slug}' is incorrect or the dataset is private/inaccessible.")
            print(f"    2. The file '{file_to_load}' does not exist within the dataset '{slug}' on Kaggle.")
            print("    3. Your kaggle.json API token is not configured correctly or lacks permissions.")
            print("    4. Network connectivity issues.")
            print(f"    If you see a '404' or 'Not Found' error, it strongly indicates problem 1 or 2.")

    print("\n--- Dataset loading and saving process finished ---")
    print(f"Please check the '{base_data_dir}' directory and its subfolders for the CSV files.")
    print("Ensure the paths in your main visualization script match this structure, for example:")
    print(f"  '{base_data_dir}/mound-villages-acre/mound_villages_acre.csv'")
    print(f"  '{base_data_dir}/archaeological-survey-data/submit.csv'")

if __name__ == "__main__":
    main()