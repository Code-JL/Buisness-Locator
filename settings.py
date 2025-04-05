from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QGroupBox, QButtonGroup, 
                               QRadioButton, QCheckBox, QScrollArea,
                               QWidget)
from PySide6.QtCore import Signal, QSettings
from PySide6.QtGui import QIcon
import os
import shutil  # Add this import for directory operations

class SettingsWindow(QDialog):
    """Settings window for configuring the application"""
    
    # Signal to notify main window when settings change
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 800)
        self.setWindowIcon(QIcon("./icons/settings.png"))
        
        # Initialize QSettings
        self.qsettings = QSettings("BuildingSizeFinder", "BuildingSizeFinder")
        
        # Set up the UI
        self.setup_ui()
        
        # Load saved settings
        self.load_settings()
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        
        # Create a scroll area to contain all settings (for better usability)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Create top row for the 2x2 grid layout
        top_row_layout = QHBoxLayout()
        
        # Location type group
        location_group = QGroupBox("Location Search Type")
        location_layout = QVBoxLayout()
        
        # Create radio buttons for location type
        self.location_type_group = QButtonGroup(self)
        
        self.coords_radio = QRadioButton("Cords (Lat/Long)")
        self.postal_radio = QRadioButton("Postal/Zip Code")
        self.city_radio = QRadioButton("City")
        
        self.location_type_group.addButton(self.coords_radio, 0)
        self.location_type_group.addButton(self.postal_radio, 1)
        self.location_type_group.addButton(self.city_radio, 2)
        
        location_layout.addWidget(self.coords_radio)
        location_layout.addWidget(self.postal_radio)
        location_layout.addWidget(self.city_radio)
        
        location_group.setLayout(location_layout)
        top_row_layout.addWidget(location_group)
        
        # Distance units group
        distance_group = QGroupBox("Distance Units")
        distance_layout = QVBoxLayout()
        
        # Create radio buttons for distance units
        self.distance_unit_group = QButtonGroup(self)
        
        self.km_radio = QRadioButton("Kilometers")
        self.mi_radio = QRadioButton("Miles")
        self.m_radio = QRadioButton("Meters")
        
        self.distance_unit_group.addButton(self.km_radio, 0)
        self.distance_unit_group.addButton(self.mi_radio, 1)
        self.distance_unit_group.addButton(self.m_radio, 2)
        
        distance_layout.addWidget(self.km_radio)
        distance_layout.addWidget(self.mi_radio)
        distance_layout.addWidget(self.m_radio)
        
        distance_group.setLayout(distance_layout)
        top_row_layout.addWidget(distance_group)
        
        # Add the top row to the main layout
        scroll_layout.addLayout(top_row_layout)
        
        # Create middle row for post-processing and spreadsheet filter (side by side)
        middle_row_layout = QHBoxLayout()
        
        # Post-processing group
        post_processing_group = QGroupBox("Post Processing")
        post_processing_layout = QVBoxLayout()
        
        # Description label
        post_processing_label = QLabel("Configure additional processing after search:")
        post_processing_label.setWordWrap(True)
        post_processing_layout.addWidget(post_processing_label)
        
        # Fetch missing addresses checkbox
        self.fetch_addresses_checkbox = QCheckBox("Fetch missing addresses")
        self.fetch_addresses_checkbox.setToolTip("Automatically look up missing addresses after search. WARNING: takes a long time, 1 second per missing address")
        post_processing_layout.addWidget(self.fetch_addresses_checkbox)
        
        # Building type filter section
        type_filter_label = QLabel("Exclude buildings by type:")
        type_filter_label.setWordWrap(True)
        post_processing_layout.addWidget(type_filter_label)
        
        # Common building types to filter
        self.type_filter_checkboxes = {}
        common_types = [
            ("residential", "Residential"),
            ("commercial", "Commercial"),
            ("industrial", "Industrial"),
            ("retail", "Retail"),
            ("office", "Office"),
            ("warehouse", "Warehouse"),
            ("garage", "Garage"),
            ("shed", "Shed"),
            ("nan", "Unknown/NaN")
        ]
        
        for type_key, type_name in common_types:
            checkbox = QCheckBox(type_name)
            checkbox.setToolTip(f"Exclude {type_name.lower()} buildings from results")
            self.type_filter_checkboxes[type_key] = checkbox
            post_processing_layout.addWidget(checkbox)
        
        post_processing_group.setLayout(post_processing_layout)
        middle_row_layout.addWidget(post_processing_group)
        
        # Spreadsheet filter group
        spreadsheet_group = QGroupBox("Spreadsheet Filter")
        spreadsheet_layout = QVBoxLayout()
        
        # Description label
        description_label = QLabel("Select which columns to display in the results table:")
        description_label.setWordWrap(True)
        spreadsheet_layout.addWidget(description_label)
        
        # Create checkboxes for each column
        self.column_checkboxes = {}
        
        # Define all available columns with their default visibility
        columns = {
            "id": ("ID", False),
            "sqft": ("Sq-Ft", True),
            "levels": ("Levels", False),
            "latitude": ("Latitude", False),
            "longitude": ("Longitude", False),
            "address": ("Address", True),
            "type": ("Type", True),
            "name": ("Name", True),
            "map": ("Map", True)
        }
        
        # Create checkbox for each column
        for column_key, (column_name, default_state) in columns.items():
            checkbox = QCheckBox(column_name)
            checkbox.setToolTip(f"Shows the {column_name.lower()} column in results")
            self.column_checkboxes[column_key] = checkbox
            spreadsheet_layout.addWidget(checkbox)
        
        spreadsheet_group.setLayout(spreadsheet_layout)
        middle_row_layout.addWidget(spreadsheet_group)
        
        # Add the middle row to the main layout
        scroll_layout.addLayout(middle_row_layout)
        
        # Add a clear cache group (bottom section)
        cache_group = QGroupBox("Cache Management")
        cache_layout = QVBoxLayout()
        
        # Description label
        cache_label = QLabel("Clear the local cache to fetch fresh data from OpenStreetMap. This can help if you're experiencing data issues.")
        cache_label.setWordWrap(True)
        cache_layout.addWidget(cache_label)
        
        # Clear cache button
        self.clear_cache_button = QPushButton("Clear OSM Cache")
        self.clear_cache_button.clicked.connect(self.clear_osm_cache)
        cache_layout.addWidget(self.clear_cache_button)
        
        cache_group.setLayout(cache_layout)
        scroll_layout.addWidget(cache_group)
        
        # Set the scroll content and add to main layout
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_settings)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Apply stylesheet
        self.apply_stylesheet()
    
    def apply_stylesheet(self):
        """Apply dark mode stylesheet to the settings window"""
        
        # Get theme colors from QSettings
        settings = QSettings("BuildingSizeFinder", "BuildingSizeFinder")
        accent_color = settings.value("theme/accent_color", "#4a86e8")
        accent_hover = settings.value("theme/accent_hover", "#5a96f8")
        accent_pressed = settings.value("theme/accent_pressed", "#3a76d8")
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #2d2d2d;
                color: #e0e0e0;
            }}
            
            QGroupBox {{
                color: #e0e0e0;
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #333333;
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                background-color: #333333;
            }}
            
            QRadioButton, QCheckBox {{
                color: #e0e0e0;
                background-color: transparent;
                padding: 4px;
            }}
            
            QRadioButton::indicator {{
                width: 13px;
                height: 13px;
            }}
            
            QRadioButton::indicator:checked {{
                background-color: {accent_color};
                border: 2px solid #e0e0e0;
                border-radius: 7px;
            }}
            
            QRadioButton::indicator:unchecked {{
                background-color: #2d2d2d;
                border: 2px solid #e0e0e0;
                border-radius: 7px;
            }}
            
            QCheckBox::indicator {{
                width: 13px;
                height: 13px;
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {accent_color};
                border: 2px solid #e0e0e0;
                border-radius: 3px;
            }}
            
            QCheckBox::indicator:unchecked {{
                background-color: #2d2d2d;
                border: 2px solid #e0e0e0;
                border-radius: 3px;
            }}
            
            QLabel {{
                color: #e0e0e0;
                background-color: transparent;
            }}
            
            QPushButton {{
                background-color: {accent_color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: {accent_hover};
            }}
            
            QPushButton:pressed {{
                background-color: {accent_pressed};
            }}
            
            QScrollArea {{
                border: none;
                background-color: #2d2d2d;
            }}
        """)
    
    def save_settings(self):
        """Save settings to QSettings"""
        # Save location type
        location_type = self.location_type_group.checkedId()
        self.qsettings.setValue("location_type", location_type)
        
        # Save distance unit based on radio button selection
        distance_unit_id = self.distance_unit_group.checkedId()
        if distance_unit_id == 0:
            distance_unit = "km"
        elif distance_unit_id == 1:
            distance_unit = "mi"
        else:  # id == 2
            distance_unit = "m"
        self.qsettings.setValue("distance_unit", distance_unit)
        
        # Save column visibility settings
        for column_key, checkbox in self.column_checkboxes.items():
            self.qsettings.setValue(f"column_visible_{column_key}", checkbox.isChecked())
        
        # Save post-processing settings
        self.qsettings.setValue("fetch_missing_addresses", self.fetch_addresses_checkbox.isChecked())
        
        # Save building type filters
        for type_key, checkbox in self.type_filter_checkboxes.items():
            self.qsettings.setValue(f"exclude_building_type_{type_key}", checkbox.isChecked())
        
        # Emit signal to notify main window
        self.settings_changed.emit()
        
        # Close the dialog
        self.accept()
    
    def load_settings(self):
        """Load settings from QSettings"""
        # Load location type (default to coordinates)
        location_type = self.qsettings.value("location_type", 0, int)
        
        # Set the appropriate radio button for location type
        if location_type == 0:
            self.coords_radio.setChecked(True)
        elif location_type == 1:
            self.postal_radio.setChecked(True)
        elif location_type == 2:
            self.city_radio.setChecked(True)
        else:
            # Default to coordinates
            self.coords_radio.setChecked(True)
        
        # Load distance unit (default to kilometers)
        distance_unit = self.qsettings.value("distance_unit", "km")
        
        # Set the appropriate radio button for distance unit
        if distance_unit == "km":
            self.km_radio.setChecked(True)
        elif distance_unit == "mi":
            self.mi_radio.setChecked(True)
        elif distance_unit == "m":
            self.m_radio.setChecked(True)
        else:
            # Default to kilometers
            self.km_radio.setChecked(True)
        
        # Load column visibility settings
        columns_default = {
            "id": False,
            "sqft": True,
            "levels": False,
            "latitude": False,
            "longitude": False,
            "address": True,
            "type": True,
            "name": True,
            "map": True
        }
        
        for column_key, checkbox in self.column_checkboxes.items():
            is_visible = self.qsettings.value(f"column_visible_{column_key}", 
                                             columns_default.get(column_key, True), 
                                             bool)
            checkbox.setChecked(is_visible)
        
        # Load post-processing settings (default to true for backward compatibility)
        fetch_addresses = self.qsettings.value("fetch_missing_addresses", False, bool)
        self.fetch_addresses_checkbox.setChecked(fetch_addresses)
        
        # Load building type filters (default to false - don't exclude anything by default)
        for type_key, checkbox in self.type_filter_checkboxes.items():
            exclude_type = self.qsettings.value(f"exclude_building_type_{type_key}", False, bool)
            checkbox.setChecked(exclude_type)
    
    @staticmethod
    def get_location_type():
        """Get the current location type setting"""
        settings = QSettings("BuildingSizeFinder", "BuildingSizeFinder")
        return settings.value("location_type", 0, int)

    def clear_osm_cache(self):
        """Clear the entire cache folder, not just osmnx subfolder"""
        try:
            # Use absolute path to the entire cache directory
            cache_folder = os.path.abspath('./cache')
            
            # Check if the directory exists
            if os.path.exists(cache_folder):
                # Count files before deletion for verification
                file_count = sum(len(files) for _, _, files in os.walk(cache_folder))
                
                # Use shutil.rmtree to remove the entire directory and recreate it
                try:
                    shutil.rmtree(cache_folder)
                    # Recreate main cache directory
                    os.makedirs(cache_folder, exist_ok=True)
                    # Also recreate the osmnx subfolder
                    os.makedirs(os.path.join(cache_folder, 'osmnx'), exist_ok=True)
                    
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.information(self, "Cache Cleared", 
                                          f"Successfully cleared {file_count} cached items.\n\n"
                                          f"New searches will fetch fresh data.")
                except Exception as e:
                    pass
                    
                    # Alternative approach: delete files individually if rmtree failed
                    success_count = 0
                    error_files = []
                    
                    for root, dirs, files in os.walk(cache_folder, topdown=False):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                os.unlink(file_path)
                                success_count += 1
                            except Exception as e:
                                error_files.append(file)
                        
                        for dir in dirs:
                            dir_path = os.path.join(root, dir)
                            try:
                                os.rmdir(dir_path)
                            except Exception as e:
                                pass
                    
                    from PySide6.QtWidgets import QMessageBox
                    if success_count > 0:
                        QMessageBox.information(self, "Partial Cache Clear", 
                                              f"Cleared {success_count} of {file_count} cached items.\n\n"
                                              f"Some files could not be deleted: {', '.join(error_files[:5])}"
                                              f"{' and more...' if len(error_files) > 5 else ''}")
                    else:
                        QMessageBox.warning(self, "Cache Clear Failed", 
                                           f"Could not clear cache files. They may be in use.\n\n"
                                           f"Try closing any other instances of the app and try again.")
            else:
                # Create directory if it doesn't exist
                os.makedirs(cache_folder, exist_ok=True)
                os.makedirs(os.path.join(cache_folder, 'osmnx'), exist_ok=True)
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "No Cache Found", 
                                       f"No cache directory found at {cache_folder}.\n"
                                       f"A new one has been created.")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Failed to clear cache: {str(e)}")
