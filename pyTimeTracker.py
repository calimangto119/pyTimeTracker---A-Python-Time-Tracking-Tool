import sys
import os
import sqlite3
import json
from datetime import datetime, timedelta

import pandas as pd

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QMessageBox, QFileDialog, QListWidget,
    QTreeWidget, QTreeWidgetItem, QComboBox, QGridLayout
)
from PyQt5.QtCore import Qt

# Attempt to import reportlab for PDF export
try:
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Configuration file path
CONFIG_FILE = 'config.json'  # JSON file for configuration

def sanitize_table_name(title):
    # Replace spaces with underscores and remove non-alphanumeric characters
    return "project_" + ''.join(e for e in title.replace(' ', '_') if e.isalnum() or e == '_')

def format_time(td):
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

class TimeTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Time Tracker")
        self.setGeometry(100, 100, 1400, 900)

        # Initialize database variables
        self.db_path = None
        self.conn = None
        self.c = None
        self.current_project_id = None
        self.current_project_table = None

        # Load configuration
        self.config = self.load_config()

        # Setup the UI
        self.setup_ui()

        # Load the last database location if available
        self.load_last_db_location()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as file:
                    config = json.load(file)
                    return config
            except json.JSONDecodeError:
                QMessageBox.critical(self, "Configuration Error", "Failed to parse config.json. Please check the file format.")
                sys.exit(1)
        else:
            # If config file doesn't exist, create a default one
            default_config = {
                "styles": {
                    "button": {
                        "background_color": "#4CAF50",
                        "hover_color": "#45a049",
                        "text_color": "white",
                        "border_radius": "10px",
                        "font_size": "16px"
                    },
                    "label": {
                        "font_size": "14px",
                        "color": "black"
                    },
                    "tree_widget": {
                        "header_background": "#d3d3d3",
                        "header_text_color": "#000000",
                        "row_background": "#FFFFFF",
                        "row_alternate_background": "#F0F0F0",
                        "grid_color": "#C0C0C0",
                        "font_size": "14px"
                    },
                    "combobox": {
                        "font_size": "14px"
                    },
                    "list_widget": {
                        "font_size": "14px"
                    }
                },
                "preferences": {
                    "default_database_path": "",
                    "enable_notifications": True,
                    "theme": "Fusion"
                }
            }
            with open(CONFIG_FILE, 'w') as file:
                json.dump(default_config, file, indent=4)
            return default_config

    def apply_styles(self):
        # Apply button styles
        button_style = f"""
            QPushButton {{
                background-color: {self.config['styles']['button']['background_color']};
                color: {self.config['styles']['button']['text_color']};
                border-radius: {self.config['styles']['button']['border_radius']};
                font-size: {self.config['styles']['button']['font_size']};
            }}
            QPushButton:hover {{
                background-color: {self.config['styles']['button']['hover_color']};
            }}
        """
        self.setStyleSheet(button_style)

        # Additional styles can be applied similarly for labels, tree widgets, etc.
        # For example, tree widget styles:
        tree_style = f"""
            QTreeWidget::item {{
                font-size: {self.config['styles']['tree_widget']['font_size']};
                background-color: {self.config['styles']['tree_widget']['row_background']};
            }}
            QTreeWidget::item:alternate {{
                background-color: {self.config['styles']['tree_widget']['row_alternate_background']};
            }}
            QTreeWidget::item:selected {{
                background-color: {self.config['styles']['button']['background_color']};
                color: {self.config['styles']['button']['text_color']};
            }}
            QHeaderView::section {{
                background-color: {self.config['styles']['tree_widget']['header_background']};
                color: {self.config['styles']['tree_widget']['header_text_color']};
                padding: 4px;
                border: 1px solid #6c6c6c;
                font-size: {self.config['styles']['tree_widget']['font_size']};
            }}
        """
        self.all_records_tree.setStyleSheet(tree_style)

        # Similarly, apply styles for other widgets like combobox and list_widget if needed.

    def setup_ui(self):
        # Create the tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create tabs
        self.tab_main_menu = QWidget()
        self.tab_start_project = QWidget()
        self.tab_continue_tracking = QWidget()
        self.tab_running_project = QWidget()
        self.tab_all_records = QWidget()

        # Add tabs to the widget
        self.tabs.addTab(self.tab_main_menu, "Main Menu")
        self.tabs.addTab(self.tab_start_project, "Start Project")
        self.tabs.addTab(self.tab_continue_tracking, "Continue Tracking")
        self.tabs.addTab(self.tab_running_project, "Running Project")
        self.tabs.addTab(self.tab_all_records, "All Records")

        # Connect tab change signal
        self.tabs.currentChanged.connect(self.on_tab_change)

        # Setup each tab
        self.setup_main_menu_tab()
        self.setup_start_project_tab()
        self.setup_continue_tracking_tab()
        self.setup_running_project_tab()
        self.setup_all_records_tab()

        # Apply styles after setting up the UI
        self.apply_styles()

    def load_last_db_location(self):
        if self.config['preferences']['default_database_path'] and os.path.exists(self.config['preferences']['default_database_path']):
            self.db_path = self.config['preferences']['default_database_path']
            try:
                self.conn = sqlite3.connect(self.db_path)
                self.c = self.conn.cursor()
                # Create master table if it doesn't exist
                self.c.execute('''CREATE TABLE IF NOT EXISTS projects_master (
                             id INTEGER PRIMARY KEY,
                             title TEXT UNIQUE,
                             details TEXT,
                             table_name TEXT UNIQUE
                             )''')
                self.conn.commit()
                # Check for any open records
                self.c.execute("SELECT id, title, table_name FROM projects_master")
                projects = self.c.fetchall()
                open_projects = []
                for proj in projects:
                    proj_id, title, table_name = proj
                    self.c.execute(f"SELECT id, start_time FROM '{table_name}' WHERE end_time IS NULL")
                    open_log = self.c.fetchone()
                    if open_log:
                        open_projects.append((proj_id, title, table_name, open_log[0], open_log[1]))
                if open_projects:
                    # Handle only the first open project for simplicity
                    open_proj = open_projects[0]
                    proj_id, title, table_name, log_id, start_time = open_proj
                    if self.current_project_id is None:
                        self.current_project_id = proj_id
                        self.current_project_table = table_name
                        # Fetch details from master table
                        self.c.execute("SELECT details FROM projects_master WHERE id = ?", (proj_id,))
                        details_fetch = self.c.fetchone()
                        details = details_fetch[0] if details_fetch else ""
                        self.update_running_project_data(title, details, start_time)
                    self.tabs.setCurrentWidget(self.tab_running_project)
                    QMessageBox.warning(self, "Warning", "An open project was found. Please stop the timer.")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Failed to connect to the database: {e}")
                self.db_path = None
        else:
            # Prompt user to select a database location if not set or invalid
            self.select_db_location()

    def select_db_location(self):
        if self.db_path is None:
            folder_selected = QFileDialog.getExistingDirectory(self, "Select Folder for Database")
            if folder_selected:
                db_path_candidate = os.path.join(folder_selected, 'projects.db')
                try:
                    self.conn = sqlite3.connect(db_path_candidate)
                    self.c = self.conn.cursor()
                    # Create master table
                    self.c.execute('''CREATE TABLE IF NOT EXISTS projects_master (
                                 id INTEGER PRIMARY KEY,
                                 title TEXT UNIQUE,
                                 details TEXT,
                                 table_name TEXT UNIQUE
                                 )''')
                    self.conn.commit()
                    # Save the selected path to the config file
                    self.config['preferences']['default_database_path'] = db_path_candidate
                    with open(CONFIG_FILE, 'w') as file:
                        json.dump(self.config, file, indent=4)
                    self.db_path = db_path_candidate
                    # Check for any open records after creating/selecting database
                    self.check_open_projects()
                except sqlite3.Error as e:
                    QMessageBox.critical(self, "Database Error", f"Failed to connect to the database: {e}")
                    self.db_path = None
            else:
                QMessageBox.warning(self, "Warning", "No folder selected. Please select a valid folder.")

    def check_open_projects(self):
        try:
            self.c.execute("SELECT id, title, table_name FROM projects_master")
            projects = self.c.fetchall()
            open_projects = []
            for proj in projects:
                proj_id, title, table_name = proj
                self.c.execute(f"SELECT id, start_time FROM '{table_name}' WHERE end_time IS NULL")
                open_log = self.c.fetchone()
                if open_log:
                    open_projects.append((proj_id, title, table_name, open_log[0], open_log[1]))
            if open_projects:
                # Handle only the first open project for simplicity
                open_proj = open_projects[0]
                proj_id, title, table_name, log_id, start_time = open_proj
                if self.current_project_id is None:
                    self.current_project_id = proj_id
                    self.current_project_table = table_name
                    # Fetch details from master table
                    self.c.execute("SELECT details FROM projects_master WHERE id = ?", (proj_id,))
                    details_fetch = self.c.fetchone()
                    details = details_fetch[0] if details_fetch else ""
                    self.update_running_project_data(title, details, start_time)
                self.tabs.setCurrentWidget(self.tab_running_project)
                QMessageBox.warning(self, "Warning", "An open project was found. Please stop the timer.")
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to check open projects: {e}")

    def setup_main_menu_tab(self):
        layout = QVBoxLayout()
        self.tab_main_menu.setLayout(layout)

        # Center the buttons
        main_menu_frame = QWidget()
        main_menu_layout = QHBoxLayout()
        main_menu_frame.setLayout(main_menu_layout)
        layout.addStretch()
        layout.addWidget(main_menu_frame, alignment=Qt.AlignCenter)
        layout.addStretch()

        # Create buttons
        btn_start_project = QPushButton("Start Project")
        btn_start_project.setFixedSize(200, 50)
        btn_start_project.clicked.connect(self.start_project_clicked)

        btn_continue_tracking = QPushButton("Continue Tracking")
        btn_continue_tracking.setFixedSize(200, 50)
        btn_continue_tracking.clicked.connect(self.continue_tracking_clicked)

        btn_view_records = QPushButton("View All Records")
        btn_view_records.setFixedSize(200, 50)
        btn_view_records.clicked.connect(self.view_all_records_clicked)

        btn_exit = QPushButton("Exit")
        btn_exit.setFixedSize(200, 50)
        btn_exit.clicked.connect(self.close)

        # Add buttons to layout
        buttons = [btn_start_project, btn_continue_tracking, btn_view_records, btn_exit]
        for btn in buttons:
            main_menu_layout.addWidget(btn)
            main_menu_layout.setSpacing(20)

    def start_project_clicked(self):
        self.select_db_location()
        self.tabs.setCurrentWidget(self.tab_start_project)

    def continue_tracking_clicked(self):
        self.select_db_location()
        self.load_projects()
        self.tabs.setCurrentWidget(self.tab_continue_tracking)

    def view_all_records_clicked(self):
        self.select_db_location()
        self.populate_filter_dropdown()
        self.display_all_records()
        self.tabs.setCurrentWidget(self.tab_all_records)

    def setup_start_project_tab(self):
        layout = QVBoxLayout()
        self.tab_start_project.setLayout(layout)

        form_layout = QGridLayout()
        layout.addLayout(form_layout)

        lbl_title = QLabel("Project Title:")
        lbl_title.setStyleSheet(f"font-size: {self.config['styles']['label']['font_size']}; color: {self.config['styles']['label']['color']};")
        self.project_title_entry = QLineEdit()
        self.project_title_entry.setFixedWidth(400)
        self.project_title_entry.setStyleSheet("font-size: 14px; padding: 5px;")

        lbl_details = QLabel("Project Details:")
        lbl_details.setStyleSheet(f"font-size: {self.config['styles']['label']['font_size']}; color: {self.config['styles']['label']['color']};")
        self.project_details_entry = QLineEdit()
        self.project_details_entry.setFixedWidth(400)
        self.project_details_entry.setStyleSheet("font-size: 14px; padding: 5px;")

        form_layout.addWidget(lbl_title, 0, 0)
        form_layout.addWidget(self.project_title_entry, 0, 1)
        form_layout.addWidget(lbl_details, 1, 0)
        form_layout.addWidget(self.project_details_entry, 1, 1)

        # Buttons
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)

        btn_start = QPushButton("Start Project")
        btn_start.setFixedSize(150, 40)
        btn_start.clicked.connect(self.start_project)

        btn_back = QPushButton("Back to Main Menu")
        btn_back.setFixedSize(200, 40)
        btn_back.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_main_menu))

        btn_exit = QPushButton("Exit")
        btn_exit.setFixedSize(100, 40)
        btn_exit.clicked.connect(self.close)

        buttons = [btn_start, btn_back, btn_exit]
        for btn in buttons:
            buttons_layout.addWidget(btn)
            buttons_layout.setSpacing(20)

    def setup_continue_tracking_tab(self):
        layout = QVBoxLayout()
        self.tab_continue_tracking.setLayout(layout)

        lbl_available = QLabel("Available Projects:")
        lbl_available.setStyleSheet(f"font-size: {self.config['styles']['label']['font_size']};")
        layout.addWidget(lbl_available, alignment=Qt.AlignCenter)

        # List Widget with scrollbar
        self.project_list_widget = QListWidget()
        self.project_list_widget.setStyleSheet(f"font-size: {self.config['styles']['list_widget']['font_size']};")
        layout.addWidget(self.project_list_widget)

        # Buttons
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)

        btn_start_recording = QPushButton("Start Recording")
        btn_start_recording.setFixedSize(150, 40)
        btn_start_recording.clicked.connect(self.start_recording)

        btn_back = QPushButton("Back to Main Menu")
        btn_back.setFixedSize(200, 40)
        btn_back.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_main_menu))

        btn_exit = QPushButton("Exit")
        btn_exit.setFixedSize(100, 40)
        btn_exit.clicked.connect(self.close)

        buttons = [btn_start_recording, btn_back, btn_exit]
        for btn in buttons:
            buttons_layout.addWidget(btn)
            buttons_layout.setSpacing(20)

    def setup_running_project_tab(self):
        layout = QVBoxLayout()
        self.tab_running_project.setLayout(layout)

        self.project_data_label = QLabel("No project running")
        self.project_data_label.setAlignment(Qt.AlignCenter)
        self.project_data_label.setStyleSheet(f"font-size: {self.config['styles']['label']['font_size']};")
        layout.addWidget(self.project_data_label)

        # Buttons
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)

        btn_stop_recording = QPushButton("Stop Recording")
        btn_stop_recording.setFixedSize(150, 40)
        btn_stop_recording.clicked.connect(self.stop_project)

        btn_back = QPushButton("Back to Main Menu")
        btn_back.setFixedSize(200, 40)
        btn_back.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_main_menu))

        btn_exit = QPushButton("Exit")
        btn_exit.setFixedSize(100, 40)
        btn_exit.clicked.connect(self.close)

        buttons = [btn_stop_recording, btn_back, btn_exit]
        for btn in buttons:
            buttons_layout.addWidget(btn)
            buttons_layout.setSpacing(20)

    def setup_all_records_tab(self):
        layout = QVBoxLayout()
        self.tab_all_records.setLayout(layout)

        # Filter Dropdown
        filter_layout = QHBoxLayout()
        layout.addLayout(filter_layout)

        lbl_filter = QLabel("Filter by Project:")
        lbl_filter.setStyleSheet(f"font-size: {self.config['styles']['label']['font_size']};")
        filter_layout.addWidget(lbl_filter)

        self.filter_combobox = QComboBox()
        self.filter_combobox.setStyleSheet(f"font-size: {self.config['styles']['combobox']['font_size']};")
        self.filter_combobox.currentIndexChanged.connect(self.on_filter_select)
        filter_layout.addWidget(self.filter_combobox)

        filter_layout.addStretch()

        # Tree Widget for records
        self.all_records_tree = QTreeWidget()
        self.all_records_tree.setColumnCount(7)
        self.all_records_tree.setHeaderLabels(["Project ID", "Title", "Details", "Start Time", "End Time", "Duration", "Cumulative Time"])
        layout.addWidget(self.all_records_tree)

        # Total Time Label
        self.total_time_label = QLabel("Total Project Time: 00h 00m 00s")
        self.total_time_label.setStyleSheet(f"font-size: {self.config['styles']['label']['font_size']};")
        layout.addWidget(self.total_time_label, alignment=Qt.AlignLeft)

        # Export Buttons
        export_buttons_layout = QHBoxLayout()
        layout.addLayout(export_buttons_layout)

        btn_export_all_excel = QPushButton("Export All to Excel")
        btn_export_all_excel.setFixedSize(180, 40)
        btn_export_all_excel.clicked.connect(lambda: self.export_to_excel(export_selected=False))

        btn_export_selected_excel = QPushButton("Export Selected to Excel")
        btn_export_selected_excel.setFixedSize(220, 40)
        btn_export_selected_excel.clicked.connect(lambda: self.export_to_excel(export_selected=True))

        btn_export_all_pdf = QPushButton("Export All to PDF")
        btn_export_all_pdf.setFixedSize(180, 40)
        btn_export_all_pdf.clicked.connect(lambda: self.export_to_pdf(export_selected=False))

        btn_export_selected_pdf = QPushButton("Export Selected to PDF")
        btn_export_selected_pdf.setFixedSize(220, 40)
        btn_export_selected_pdf.clicked.connect(lambda: self.export_to_pdf(export_selected=True))

        btn_back = QPushButton("Back to Main Menu")
        btn_back.setFixedSize(200, 40)
        btn_back.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_main_menu))

        btn_exit = QPushButton("Exit")
        btn_exit.setFixedSize(100, 40)
        btn_exit.clicked.connect(self.close)

        export_buttons = [
            btn_export_all_excel, btn_export_selected_excel,
            btn_export_all_pdf, btn_export_selected_pdf,
            btn_back, btn_exit
        ]

        for btn in export_buttons:
            export_buttons_layout.addWidget(btn)
            export_buttons_layout.setSpacing(10)

    def update_running_project_data(self, title, details, start_time_str):
        self.project_data_label.setText(f"Project: {title}\nDetails: {details}\nStart Time: {start_time_str}")

    def start_project(self):
        title = self.project_title_entry.text().strip()
        details = self.project_details_entry.text().strip()
        if title:
            try:
                # Check if project title already exists
                self.c.execute("SELECT id FROM projects_master WHERE title = ?", (title,))
                if self.c.fetchone():
                    QMessageBox.warning(self, "Warning", "A project with this title already exists.")
                    return

                # Generate sanitized table name
                table_name = sanitize_table_name(title)

                # Create a table for the project
                self.c.execute(f'''
                    CREATE TABLE IF NOT EXISTS "{table_name}" (
                        id INTEGER PRIMARY KEY,
                        start_time TEXT,
                        end_time TEXT,
                        duration TEXT,
                        cumulative_time TEXT
                    )
                ''')
                self.conn.commit()

                # Insert project metadata into master table
                self.c.execute("INSERT INTO projects_master (title, details, table_name) VALUES (?, ?, ?)",
                              (title, details, table_name))
                self.conn.commit()
                self.current_project_id = self.c.lastrowid
                self.current_project_table = table_name

                # Log the start time in the project-specific table
                start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.c.execute(f"INSERT INTO '{table_name}' (start_time) VALUES (?)", (start_time,))
                self.conn.commit()

                # Update running project data
                self.update_running_project_data(title, details, start_time)
                self.load_projects()  # Refresh project list on start
                self.populate_filter_dropdown()  # Refresh dropdown in All Records tab
                self.tabs.setCurrentWidget(self.tab_running_project)
                QMessageBox.information(self, "Started", f"Started tracking time for project: {title}")
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Warning", "A project with this title or table name already exists.")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Failed to start project: {e}")
        else:
            QMessageBox.warning(self, "Input Error", "Please enter a project title.")

    def stop_project(self):
        if self.current_project_id and self.current_project_table:
            try:
                # Find the last log entry without end_time
                self.c.execute(f"SELECT id, start_time FROM '{self.current_project_table}' WHERE end_time IS NULL ORDER BY id DESC LIMIT 1")
                log_entry = self.c.fetchone()
                if log_entry:
                    log_id, start_time_str = log_entry
                    start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
                    end_time_dt = datetime.now()
                    end_time_str = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")
                    duration = end_time_dt - start_time_dt
                    duration_str = str(duration).split('.')[0]  # Remove microseconds

                    # Calculate cumulative_time by summing all previous durations
                    self.c.execute(f"SELECT duration FROM '{self.current_project_table}' WHERE id < ? AND duration IS NOT NULL", (log_id,))
                    previous_durations = self.c.fetchall()
                    total_seconds = 0
                    for dur in previous_durations:
                        try:
                            h, m, s = map(int, dur[0].split(':'))
                            total_seconds += h * 3600 + m * 60 + s
                        except:
                            continue  # In case of malformed duration
                    # Add current duration
                    duration_seconds = int(duration.total_seconds())
                    new_cumulative_seconds = total_seconds + duration_seconds
                    cumulative_time_str = f"{new_cumulative_seconds // 3600:02d}:{(new_cumulative_seconds % 3600) // 60:02d}:{new_cumulative_seconds % 60:02d}"

                    # Update the project-specific table
                    self.c.execute(f"UPDATE '{self.current_project_table}' SET end_time = ?, duration = ?, cumulative_time = ? WHERE id = ?",
                                  (end_time_str, duration_str, cumulative_time_str, log_id))
                    self.conn.commit()

                    QMessageBox.information(self, "Stopped", f"Stopped tracking time for project ID {self.current_project_id}")
                    self.current_project_id = None
                    self.current_project_table = None
                    self.load_projects()  # Refresh project list on stop
                    self.populate_filter_dropdown()  # Refresh dropdown in All Records tab
                    self.tabs.setCurrentWidget(self.tab_main_menu)  # Go back to main menu
                    # Reset Running Project tab label
                    self.project_data_label.setText("No project running")
                else:
                    QMessageBox.warning(self, "Warning", "No active time log found for this project.")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Failed to stop project: {e}")
        else:
            QMessageBox.warning(self, "Warning", "No project is currently running.")

    def start_recording(self):
        selected_items = self.project_list_widget.selectedItems()
        if selected_items:
            project_title = selected_items[0].text()
            if project_title != "No available projects to track.":
                try:
                    # Fetch project details from master table
                    self.c.execute("SELECT id, details, table_name FROM projects_master WHERE title = ?", (project_title,))
                    result = self.c.fetchone()
                    if result:
                        proj_id, details, table_name = result
                    else:
                        QMessageBox.critical(self, "Error", "Project not found in the database.")
                        return

                    # Check if there's an ongoing time log
                    self.c.execute(f"SELECT COUNT(*) FROM '{table_name}' WHERE end_time IS NULL")
                    count = self.c.fetchone()[0]
                    if count > 0:
                        QMessageBox.warning(self, "Warning", "This project is already being tracked.")
                        return

                    # Start a new tracking session
                    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.c.execute(f"INSERT INTO '{table_name}' (start_time) VALUES (?)", (start_time,))
                    self.conn.commit()
                    self.current_project_id = proj_id
                    self.current_project_table = table_name
                    self.update_running_project_data(project_title, details, start_time)
                    self.tabs.setCurrentWidget(self.tab_running_project)
                    QMessageBox.information(self, "Started", f"Started tracking time for project: {project_title}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to start recording: {e}")
        else:
            QMessageBox.warning(self, "Warning", "Please select a project to start tracking.")

    def load_projects(self):
        self.project_list_widget.clear()
        try:
            # Query the master table for all projects
            self.c.execute("SELECT title FROM projects_master ORDER BY title ASC")
            projects = self.c.fetchall()
            available_projects = []
            for proj in projects:
                title = proj[0]
                table_name = sanitize_table_name(title)
                self.c.execute(f"SELECT COUNT(*) FROM '{table_name}' WHERE end_time IS NULL")
                count = self.c.fetchone()[0]
                if count == 0:
                    available_projects.append(title)

            if available_projects:
                for title in available_projects:
                    self.project_list_widget.addItem(title)
            else:
                self.project_list_widget.addItem("No available projects to track.")
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load projects: {e}")

    def populate_filter_dropdown(self):
        try:
            self.c.execute("SELECT title FROM projects_master ORDER BY title ASC")
            projects = [row[0] for row in self.c.fetchall()]
            values = ["All Projects"] + projects
            self.filter_combobox.clear()
            self.filter_combobox.addItems(values)
            self.filter_combobox.setCurrentIndex(0)  # Set default to "All Projects"
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load projects for filtering: {e}")

    def on_filter_select(self):
        selected = self.filter_combobox.currentText()
        if selected == "All Projects":
            self.display_all_records()
        else:
            # Get project ID based on selected title
            proj_id = self.get_project_id(selected)
            if proj_id:
                self.display_all_records(filter_project_id=proj_id)
            else:
                self.display_all_records()

    def display_all_records(self, filter_project_id=None):
        # Clear existing data in Treeview
        self.all_records_tree.clear()
        self.all_records_tree.setHeaderLabels(["Project ID", "Title", "Details", "Start Time", "End Time", "Duration", "Cumulative Time"])
        try:
            if filter_project_id:
                # Fetch only the selected project's records
                self.c.execute("SELECT title, details FROM projects_master WHERE id = ?", (filter_project_id,))
                project = self.c.fetchone()
                if project:
                    title, details = project
                    table_name = sanitize_table_name(title)
                    self.c.execute(f"SELECT start_time, end_time, duration, cumulative_time FROM '{table_name}'")
                    logs = self.c.fetchall()
                    if logs:
                        for log in logs:
                            start_time, end_time, duration, cumulative_time = log
                            end_time_str = end_time if end_time else "In Progress"
                            duration_str = duration if duration else "N/A"
                            cumulative_time_str = cumulative_time if cumulative_time else "N/A"
                            self.all_records_tree.addTopLevelItem(QTreeWidgetItem([
                                str(filter_project_id), title, details,
                                start_time, end_time_str, duration_str, cumulative_time_str
                            ]))
                    else:
                        self.all_records_tree.addTopLevelItem(QTreeWidgetItem([
                            str(filter_project_id), title, details,
                            "N/A", "N/A", "N/A", "N/A"
                        ]))
            else:
                # Fetch all records
                self.c.execute("SELECT id, title, details FROM projects_master")
                projects = self.c.fetchall()
                for project in projects:
                    proj_id, title, details = project
                    table_name = sanitize_table_name(title)
                    self.c.execute(f"SELECT start_time, end_time, duration, cumulative_time FROM '{table_name}'")
                    logs = self.c.fetchall()
                    if logs:
                        for log in logs:
                            start_time, end_time, duration, cumulative_time = log
                            end_time_str = end_time if end_time else "In Progress"
                            duration_str = duration if duration else "N/A"
                            cumulative_time_str = cumulative_time if cumulative_time else "N/A"
                            self.all_records_tree.addTopLevelItem(QTreeWidgetItem([
                                str(proj_id), title, details,
                                start_time, end_time_str, duration_str, cumulative_time_str
                            ]))
                    else:
                        self.all_records_tree.addTopLevelItem(QTreeWidgetItem([
                            str(proj_id), title, details,
                            "N/A", "N/A", "N/A", "N/A"
                        ]))
            # Update total time
            self.update_total_time(filter_project_id)
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load all records: {e}")

    def update_total_time(self, filter_project_id=None):
        total_seconds = 0
        try:
            if filter_project_id:
                project_title = self.get_project_title(filter_project_id)
                table_name = sanitize_table_name(project_title)
                self.c.execute(f"SELECT duration FROM '{table_name}'")
                durations = self.c.fetchall()
            else:
                self.c.execute("SELECT table_name FROM projects_master")
                tables = self.c.fetchall()
                durations = []
                for table in tables:
                    table_name = table[0]
                    self.c.execute(f"SELECT duration FROM '{table_name}'")
                    durations += self.c.fetchall()
            for dur in durations:
                duration_str = dur[0]
                if duration_str and duration_str != "N/A":
                    try:
                        h, m, s = map(int, duration_str.split(':'))
                        total_seconds += h * 3600 + m * 60 + s
                    except:
                        continue  # Skip malformed duration entries
            formatted_total = format_time(timedelta(seconds=total_seconds))
            self.total_time_label.setText(f"Total Project Time: {formatted_total}")
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Failed to calculate total time: {e}")

    def get_project_title(self, proj_id):
        self.c.execute("SELECT title FROM projects_master WHERE id = ?", (proj_id,))
        result = self.c.fetchone()
        return result[0] if result else ""

    def get_project_id(self, title):
        self.c.execute("SELECT id FROM projects_master WHERE title = ?", (title,))
        result = self.c.fetchone()
        return result[0] if result else None

    def export_to_excel(self, export_selected=False):
        if self.db_path:
            try:
                records = self.get_records_to_export(export_selected)
                if export_selected and not records:
                    QMessageBox.warning(self, "Warning", "No records selected for export.")
                    return

                # Determine export type based on whether records are selected
                title_dialog = "Save Selected Records to Excel" if export_selected else "Save All Records to Excel"

                save_path, _ = QFileDialog.getSaveFileName(self, title_dialog, "", "Excel Files (*.xlsx)")
                if save_path:
                    with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
                        # Prepare data for the Excel sheet
                        data = self.prepare_data_for_export(records)
                        if data:
                            df = pd.DataFrame(data[1:], columns=data[0])  # Exclude headers from data
                            df.to_excel(writer, sheet_name='Project Records', index=False)
                        else:
                            # Create an empty DataFrame with headers
                            df = pd.DataFrame(columns=["Project ID", "Title", "Details", "Start Time", "End Time", "Duration", "Cumulative Time"])
                            df.to_excel(writer, sheet_name='Project Records', index=False)

                    QMessageBox.information(self, "Success", f"Records exported to Excel:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export to Excel: {e}")
        else:
            QMessageBox.warning(self, "Warning", "No database connected.")

    def export_to_pdf(self, export_selected=False):
        if not REPORTLAB_AVAILABLE:
            QMessageBox.critical(self, "Error", "ReportLab library is not installed. Please install it using 'pip install reportlab'")
            return

        if self.db_path:
            try:
                records = self.get_records_to_export(export_selected)
                if export_selected and not records:
                    QMessageBox.warning(self, "Warning", "No records selected for export.")
                    return

                # Determine export type based on whether records are selected
                title_dialog = "Save Selected Records to PDF" if export_selected else "Save All Records to PDF"

                save_path, _ = QFileDialog.getSaveFileName(self, title_dialog, "", "PDF Files (*.pdf)")
                if save_path:
                    doc = SimpleDocTemplate(save_path, pagesize=landscape(letter))
                    elements = []
                    styles = getSampleStyleSheet()

                    # Add title
                    elements.append(Paragraph("Selected Project Records" if export_selected else "All Project Records", styles['Title']))
                    elements.append(Spacer(1, 12))

                    # Prepare data for the PDF table
                    data = self.prepare_data_for_export(records)
                    if data:
                        t = Table(data, repeatRows=1)
                        t.setStyle(TableStyle([
                            ('BACKGROUND', (0,0), (-1,0), colors.gray),
                            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                            ('BOTTOMPADDING', (0,0), (-1,0), 12),
                            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                            ('GRID', (0,0), (-1,-1), 1, colors.black),
                        ]))
                        elements.append(t)
                        elements.append(Spacer(1, 12))
                    else:
                        elements.append(Paragraph("No records found for export.", styles['Normal']))
                        elements.append(Spacer(1, 12))

                    # Build PDF
                    doc.build(elements)
                    QMessageBox.information(self, "Success", f"Records exported to PDF:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export to PDF: {e}")
        else:
            QMessageBox.warning(self, "Warning", "No database connected.")

    def get_records_to_export(self, export_selected=False):
        """
        Retrieves records to export based on the export_selected flag.
        If export_selected is True, returns only the selected records.
        Otherwise, returns all records currently displayed in the Treeview.
        """
        if export_selected:
            selected_items = self.all_records_tree.selectedItems()
            records = []
            for item in selected_items:
                values = [item.text(i) for i in range(self.all_records_tree.columnCount())]
                records.append(values)
            return records
        else:
            # Get all records currently displayed in the Treeview
            records = []
            for i in range(self.all_records_tree.topLevelItemCount()):
                item = self.all_records_tree.topLevelItem(i)
                values = [item.text(j) for j in range(self.all_records_tree.columnCount())]
                records.append(values)
            return records

    def prepare_data_for_export(self, records):
        """
        Formats the list of records into a structured format suitable for exporting.
        Returns a list of lists, where each sublist represents a row.
        """
        if not records:
            return []

        # Extract headers from the Treeview columns
        headers = ["Project ID", "Title", "Details", "Start Time", "End Time", "Duration", "Cumulative Time"]
        data = [headers]

        for record in records:
            data.append(list(record))

        return data

    def display_all_records_tab(self, filter_project_id=None):
        """
        This method is intentionally kept separate to avoid confusion with the existing display_all_records method.
        """
        self.display_all_records(filter_project_id)

    def on_tab_change(self, index):
        selected_tab = self.tabs.tabText(index)

        if selected_tab == "Start Project":
            self.select_db_location()
        elif selected_tab == "Continue Tracking":
            self.select_db_location()
            self.load_projects()
        elif selected_tab == "All Records":
            self.select_db_location()
            self.populate_filter_dropdown()
            self.display_all_records()
        elif selected_tab == "Running Project":
            if self.current_project_id and self.current_project_table:
                # Optionally, refresh the running project data
                self.update_running_project_data_tab()
            else:
                self.project_data_label.setText("No project running")

    def update_running_project_data_tab(self):
        if self.current_project_id and self.current_project_table:
            # Fetch project details
            self.c.execute("SELECT title, details FROM projects_master WHERE id = ?", (self.current_project_id,))
            result = self.c.fetchone()
            if result:
                title, details = result
                # Fetch start time
                self.c.execute(f"SELECT start_time FROM '{self.current_project_table}' WHERE end_time IS NULL LIMIT 1")
                start_time_fetch = self.c.fetchone()
                start_time = start_time_fetch[0] if start_time_fetch else "N/A"
                self.update_running_project_data(title, details, start_time)
        else:
            self.project_data_label.setText("No project running")

    def closeEvent(self, event):
        # Close the database connection when the application is closed
        if self.db_path and self.conn:
            self.conn.close()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Optional: Use Fusion style for a modern look
    window = TimeTrackerApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
