# Project Brief: Amazon Archaeology Project Restructuring

## 1. Project Overview

The primary goal of this project is to assist the user in restructuring their existing Python-based geospatial analysis project related to Amazonian archaeology. The current state involves a collection of scripts and research materials in a flat or disorganized structure.

## 2. Core Requirements & Goals

The user requires a set of clear, step-by-step instructions to:
1.  **Define and Create a Logical Folder Structure:** Implement a simple, intuitive directory hierarchy to organize scripts, data, and research materials.
2.  **Relocate Existing Files:** Move current Python scripts and research documents into the new structure.
3.  **Update Script Path References:** Identify and provide updated file path references within the Python scripts to ensure they function correctly from their new locations, assuming scripts are run from the project root.

## 3. Guiding Principles

The restructuring process must adhere to:
*   **KISS (Keep It Super Simple):** The folder structure should be minimal and intuitive. Path changes should be direct.
*   **YAGNI (You Ain't Gonna Need It):** No new abstractions, helper functions, config files, or splitting of script logic. Scripts should remain functionally identical, with only their location and internal path strings changing.
*   **Focus:** The primary aim is to make files easy to find and the project more manageable.

## 4. Scope of Work (LLM's Task)

The LLM (Cline) will generate a markdown document for the user, containing:
1.  The definition of the target directory structure.
2.  A list of `mkdir` commands to create this structure.
3.  A list of `mv` (move) commands to relocate files.
4.  Detailed instructions for updating file paths within each moved Python script (excluding those moved to an `old/` directory).

## 5. Inputs Required from User (for LLM to complete its task)

*   The project context, challenge description, and methodological paper (already partially provided).
*   A complete list of all Python filenames currently in the project.
*   The full content of each of these Python scripts.
*   Specific current filenames for:
    *   "OpenAI to Z Challenge" description.
    *   The user's "Methodological Approach" paper.
    *   The "Bibliography".

## 6. Target Directory Structure (Pre-defined)

```
project_root/
├── old/
├── data_preparation/
├── terrain_analysis/
├── visualization/
├── research_materials/
├── input_data/
│   ├── dem/
│   └── known_sites/
├── output_data/
│   ├── processed_dem/
│   ├── interfluves/
│   ├── maps/
│   └── intermediate_outputs/
├── README.md
└── .gitignore
```

This brief will serve as the foundation for subsequent Memory Bank documents.
