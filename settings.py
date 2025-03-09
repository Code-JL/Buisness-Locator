from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QPushButton, QGroupBox, QFormLayout,
                               QButtonGroup, QRadioButton, QCheckBox, QScrollArea,
                               QWidget)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QIcon

class SettingsWindow(QDialog):
    """Settings window for configuring the application"""
    
    # Signal to notify main window when settings change
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(400, 500)
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
        
        # Spreadsheet filter group (spans full width at bottom)
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
            "id": ("ID", True),  
            "sqft": ("Sq-Ft", True),
            "levels": ("Levels", False),  # Off by default
            "latitude": ("Latitude", False),  # Off by default
            "longitude": ("Longitude", False),  # Off by default
            "address": ("Address", True),
            "type": ("Type", True),
            "usage": ("Usage", True),
            "name": ("Name", True)
        }
        
        # Create checkbox for each column
        for column_key, (column_name, default_state) in columns.items():
            checkbox = QCheckBox(column_name)
            self.column_checkboxes[column_key] = checkbox
            spreadsheet_layout.addWidget(checkbox)
        
        spreadsheet_group.setLayout(spreadsheet_layout)
        scroll_layout.addWidget(spreadsheet_group)
        
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
        self.setStyleSheet("""
            QDialog {
                background-color: #2d2d2d;
                color: #e0e0e0;
            }
            
            QGroupBox {
                color: #e0e0e0;
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #333333;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                background-color: #333333;
            }
            
            QRadioButton, QCheckBox {
                color: #e0e0e0;
                background-color: transparent;
                padding: 4px;
            }
            
            QRadioButton::indicator {
                width: 13px;
                height: 13px;
            }
            
            QRadioButton::indicator:checked {
                background-color: #4a86e8;
                border: 2px solid #e0e0e0;
                border-radius: 7px;
            }
            
            QRadioButton::indicator:unchecked {
                background-color: #2d2d2d;
                border: 2px solid #e0e0e0;
                border-radius: 7px;
            }
            
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            
            QCheckBox::indicator:checked {
                background-color: #4a86e8;
                border: 2px solid #e0e0e0;
                border-radius: 3px;
            }
            
            QCheckBox::indicator:unchecked {
                background-color: #2d2d2d;
                border: 2px solid #e0e0e0;
                border-radius: 3px;
            }
            
            QLabel {
                color: #e0e0e0;
                background-color: transparent;
            }
            
            QPushButton {
                background-color: #4a86e8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #5a96f8;
            }
            
            QPushButton:pressed {
                background-color: #3a76d8;
            }
            
            QScrollArea {
                border: none;
                background-color: #2d2d2d;
            }
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
            "id": True,  
            "sqft": True,
            "levels": False,  # Off by default
            "latitude": False,  # Off by default
            "longitude": False,  # Off by default
            "address": True,
            "type": True,
            "usage": True,
            "name": True
        }
        
        for column_key, checkbox in self.column_checkboxes.items():
            is_visible = self.qsettings.value(f"column_visible_{column_key}", 
                                             columns_default.get(column_key, True), 
                                             bool)
            checkbox.setChecked(is_visible)
    
    @staticmethod
    def get_location_type():
        """Get the current location type setting"""
        settings = QSettings("BuildingSizeFinder", "BuildingSizeFinder")
        return settings.value("location_type", 0, int)
