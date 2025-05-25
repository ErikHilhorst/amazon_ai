# System Patterns: Project Restructuring

## 1. Core Architectural Decision: Standardized Directory Structure

The fundamental pattern for this project restructuring is the adoption of a predefined, hierarchical directory structure. This structure (detailed in `projectbrief.md`) aims to:
*   **Separate Concerns:** Group files by their role (e.g., data preparation scripts, analysis scripts, raw input data, generated output data, research materials).
*   **Improve Navigability:** Make it easier for the user to locate specific project assets.
*   **Establish Conventions:** Provide a consistent framework for where files should be placed.

## 2. Key Technical Pattern: Root-Relative Pathing and Execution

*   **Execution Context:** All Python scripts, once moved, are assumed to be executed from the project's root directory.
    *   Example: `python data_preparation/my_script.py` (NOT `cd data_preparation; python my_script.py`)
*   **Path Referencing:** Consequently, all file paths within the Python scripts must be updated to be relative to the project root.
    *   Example (Old, script in root): `input_file = "my_data.csv"`
    *   Example (New, script in `data_preparation/`, data in `input_data/`): `input_file = "input_data/my_data.csv"`
*   **No Complex Path Management:** Adhering to YAGNI, the plan will not introduce:
    *   Configuration files for paths.
    *   Environment variables for base directories (beyond what the user might already employ).
    *   Dynamic path construction using `os.path.join(os.path.dirname(__file__), ...)` for this restructuring exercise. The goal is simple, direct string replacement for existing path literals.

## 3. File Categorization Logic

Scripts and materials will be categorized based on:
*   **Script Naming Conventions:** Filenames suggesting versioning (e.g., `_v1`, `_old`), testing, or backup status will be moved to `old/`.
*   **Script Content Analysis:** Keywords, imported libraries (e.g., `ee`, `rasterio`, `whitebox`, `folium`, `matplotlib`), and operations described in the user's methodological paper will determine placement into `data_preparation/`, `terrain_analysis/`, or `visualization/`.
*   **Primary Function/Output:** If a script spans multiple conceptual categories, its primary output or final processing step will guide its categorization.
*   **Research Materials:** Non-code assets like the challenge description, methodological paper, and bibliography will be placed in `research_materials/`.

## 4. Data Flow Assumption

*   **Input Data:** Raw input data (e.g., DEMs, shapefiles of known sites) will reside in `input_data/` and its subdirectories. Scripts in `data_preparation/` might download or initially process these.
*   **Output Data:** Processed data (e.g., filled DEMs, interfluve rasters, maps) will be saved to `output_data/` and its subdirectories. Scripts in `terrain_analysis/` and `visualization/` will primarily generate these outputs. Intermediate outputs that are saved and potentially reused will go into `output_data/intermediate_outputs/`.

This system pattern emphasizes simplicity and directness, aligning with the KISS and YAGNI principles outlined in the `projectbrief.md`.
