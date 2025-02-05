# Time Tracker Application

A desktop time tracker built with Python and PyQt5. This application lets you start new projects, continue tracking ongoing projects, and view or export all tracking records. It uses an SQLite database to store project data and time logs, and you can export records to Excel or PDF (with ReportLab installed).

## Overview

The Time Tracker application provides a user-friendly interface to manage project time tracking. It includes the following features:

- **Start a New Project:** Create a project by entering a title and details. A dedicated database table is created for each project.
- **Continue Tracking:** Resume tracking for projects that aren’t currently active.
- **Running Project:** View details of the currently active project, including start time.
- **All Records:** Review all project logs in a table format with options to filter by project.
- **Export Records:** Export tracking records to Excel (via Pandas) or PDF (via ReportLab).

The application also reads a configuration file (`config.json`) for UI styles and preferences. If the file does not exist, a default configuration is created.

## Key Features

- **Multi-Tab Interface:**  
  - **Main Menu:** Navigate to start, continue, or view projects.  
  - **Start Project:** Input project title and details, then begin tracking.  
  - **Continue Tracking:** View a list of projects available for resuming tracking.  
  - **Running Project:** Displays active project details and tracking start time.  
  - **All Records:** Displays a log of all projects with filtering and export options.

- **Database Integration:**  
  - Uses SQLite to store project metadata and individual time logs.
  - Prompts for and saves the database location on first use.

- **Configurable UI:**  
  - Loads style and preference settings from `config.json`.
  - Default styles include button colors, fonts, and widget layouts.

- **Export Functionality:**  
  - **Excel Export:** Uses Pandas and OpenPyXL to export records.
  - **PDF Export:** Uses ReportLab to export records to PDF (requires installation).

## Installation and Requirements

Make sure you have Python installed along with the following packages:

- [PyQt5](https://pypi.org/project/PyQt5/)
- [pandas](https://pypi.org/project/pandas/)
- (Optional) [reportlab](https://pypi.org/project/reportlab/) – required for PDF export
- (Optional) [openpyxl](https://pypi.org/project/openpyxl/) – required for Excel export

## Disclaimer
This software is provided "as-is" without any warranty. The author is not liable for any damages or issues arising from its use.

