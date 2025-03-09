import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
                              QHeaderView, QSpinBox, QDoubleSpinBox, QProgressBar, QMessageBox,
                              QSplitter, QGroupBox, QFormLayout, QToolBar, QComboBox, QSizePolicy)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSettings, QSize
from PySide6.QtGui import QIcon, QFont, QColor, QAction

# Import your building size function
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from buildings.getSize import get_buildings_by_size, process_large_area
from settings import SettingsWindow

# Import geocoding functions
import pgeocode
import time
from geopy.geocoders import Nominatim
import pandas as pd

class BuildingSearchWorker(QThread):
    """Worker thread to run the building search without freezing the UI"""
    finished = Signal(dict)
    progress = Signal(str)
    
    def __init__(self, longitude, latitude, min_sqft, radius):
        super().__init__()
        self.longitude = longitude
        self.latitude = latitude
        self.min_sqft = min_sqft
        self.radius = radius
        
    def run(self):
        self.progress.emit("Searching for buildings...")
        
        if self.radius <= 500:
            result = get_buildings_by_size(self.longitude, self.latitude, self.min_sqft, self.radius)
        else:
            self.progress.emit("Large radius detected. Using optimized search...")
            result = process_large_area(self.longitude, self.latitude, self.min_sqft, self.radius)
            
        self.finished.emit(result)

class BuildingSizeFinderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Building Locator")
        self.setMinimumSize(800, 600)
        
        # Load settings
        self.settings = QSettings("BuildingSizeFinder", "BuildingSizeFinder")
        
        # Restore window geometry from settings
        self.restoreGeometry(self.settings.value("windowGeometry", b""))
        self.restoreState(self.settings.value("windowState", b""))
        
        # Create toolbar with settings icon
        self.create_toolbar()
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create a splitter for the top and bottom sections
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # Top section - Search parameters
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        # Title
        title_label = QLabel("Building Locator")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        top_layout.addWidget(title_label)
        
        # Form Group
        self.form_group = QGroupBox("Search Parameters")
        self.form_layout = QFormLayout()
        
        # Create location input widgets (will be populated based on settings)
        self.create_location_inputs()
        
        self.form_group.setLayout(self.form_layout)
        top_layout.addWidget(self.form_group)
        
        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.setFixedHeight(40)
        self.search_button.clicked.connect(self.start_search)
        top_layout.addWidget(self.search_button)
        
        # Status display
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.hide()
        top_layout.addWidget(self.progress_bar)
        
        # Bottom section - Results
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        # Results label
        results_label = QLabel("Search Results")
        results_font = QFont()
        results_font.setPointSize(14)
        results_font.setBold(True)
        results_label.setFont(results_font)
        results_label.setAlignment(Qt.AlignCenter)
        bottom_layout.addWidget(results_label)
        
        # Results count
        self.results_count = QLabel("No results yet")
        self.results_count.setAlignment(Qt.AlignCenter)
        bottom_layout.addWidget(self.results_count)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(9)
        self.results_table.setHorizontalHeaderLabels([
            "ID", "Sq-Ft", "Levels", "Latitude", "Longitude", "Address", "Type", "Usage", "Name"
        ])
        
        # Store column indexes for easier reference
        self.column_indexes = {
            "id": 0,
            "sqft": 1,
            "levels": 2,
            "latitude": 3,
            "longitude": 4,
            "address": 5,
            "type": 6,
            "usage": 7,
            "name": 8
        }
        
        # Apply column visibility based on settings
        self.apply_column_visibility()
        
        # Set percentage-based column widths for visible columns
        self.update_column_percentages()
        
        # Connect column resize signal to track user resizing
        header = self.results_table.horizontalHeader()
        header.sectionResized.connect(self.recalculate_column_widths)
        
        # Install event filter for table resize events
        self.results_table.resizeEvent = self.handle_table_resize
        
        bottom_layout.addWidget(self.results_table)
        
        # Add widgets to splitter
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        # Apply a comprehensive dark mode stylesheet
        self.setStyleSheet("""
            /* Main application background */
            QMainWindow, QWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
            }
            
            /* Form elements */
            QLabel {
                color: #e0e0e0;
                background-color: transparent;
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
            
            /* Input fields */
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #3d3d3d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
                selection-background-color: #4a86e8;
            }
            
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left-width: 1px;
                border-left-color: #555555;
                border-left-style: solid;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }
            
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
                background: #e0e0e0;
            }
            
            QComboBox QAbstractItemView {
                border: 1px solid #555555;
                selection-background-color: #4a86e8;
                background-color: #3d3d3d;
                color: #e0e0e0;
            }
            
            /* Buttons */
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
            
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
            
            /* Table styling */
            QTableWidget {
                background-color: #2d2d2d;
                alternate-background-color: #353535;
                color: #e0e0e0;
                gridline-color: #555555;
                border: 1px solid #555555;
                border-radius: 3px;
            }
            
            QTableWidget::item {
                padding: 4px;
                border: none;
            }
            
            QTableWidget::item:selected {
                background-color: #4a86e8;
                color: white;
            }
            
            QHeaderView::section {
                background-color: #3d3d3d;
                color: #e0e0e0;
                padding: 5px;
                border: 1px solid #555555;
                font-weight: bold;
            }
            
            /* Scrollbars */
            QScrollBar:vertical, QScrollBar:horizontal {
                background-color: #2d2d2d;
                border: none;
                width: 12px;
                height: 12px;
            }
            
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background-color: #666666;
            }
            
            /* Progress bar */
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 3px;
                background-color: #3d3d3d;
                text-align: center;
                color: #e0e0e0;
            }
            
            QProgressBar::chunk {
                background-color: #4a86e8;
                width: 10px;
            }
            
            /* Splitter */
            QSplitter::handle {
                background-color: #555555;
            }
            
            QSplitter::handle:horizontal {
                width: 2px;
            }
            
            QSplitter::handle:vertical {
                height: 2px;
            }
            
            /* Toolbar */
            QToolBar {
                background-color: #333333;
                border: none;
                spacing: 3px;
            }
            
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 3px;
                padding: 5px;
            }
            
            QToolButton:hover {
                background-color: #4a4a4a;
            }
            
            QToolButton:pressed {
                background-color: #555555;
            }
        """)
    
    def create_toolbar(self):
        """Create the toolbar with settings icon"""
        toolbar = QToolBar("Settings")
        toolbar.setObjectName("settingsToolbar")
        toolbar.setIconSize(QSize(24, 24))
        
        # Create spacer to push settings icon to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # Create settings action
        settings_action = QAction(QIcon("./icons/settings.png"), "Settings", self)
        settings_action.triggered.connect(self.show_settings)
        
        # Add widgets to toolbar
        toolbar.addWidget(spacer)
        toolbar.addAction(settings_action)
        
        self.addToolBar(toolbar)
    
    def show_settings(self):
        """Show the settings dialog"""
        settings_dialog = SettingsWindow(self)
        settings_dialog.settings_changed.connect(self.on_settings_changed)
        settings_dialog.exec()
    
    def on_settings_changed(self):
        """Handle settings changes"""
        # Update the UI based on the new settings
        self.create_location_inputs()
        
        # Apply column visibility settings
        self.apply_column_visibility()
    
    def create_location_inputs(self):
        """Create location input widgets based on current settings"""
        # Store the current values of sqft and radius
        current_sqft = 5000
        current_radius = 500
        
        if hasattr(self, 'sqft_input'):
            current_sqft = self.sqft_input.value()
        
        if hasattr(self, 'radius_input'):
            current_radius = self.radius_input.value()
        
        # Clear existing widgets from form layout
        while self.form_layout.rowCount() > 0:
            self.form_layout.removeRow(0)
        
        # Get current location type
        location_type = self.settings.value("location_type", 0, int)
        
        if location_type == 0:  # Coordinates
            # Latitude input
            self.latitude_input = QDoubleSpinBox()
            self.latitude_input.setRange(-90, 90)
            self.latitude_input.setDecimals(6)
            self.latitude_input.setValue(40.7484)  # Default: New York City
            self.form_layout.addRow("Latitude:", self.latitude_input)
            
            # Longitude input
            self.longitude_input = QDoubleSpinBox()
            self.longitude_input.setRange(-180, 180)
            self.longitude_input.setDecimals(6)
            self.longitude_input.setValue(-73.9967)  # Default: New York City
            self.form_layout.addRow("Longitude:", self.longitude_input)
            
        elif location_type == 1:  # Postal/Zip Code
            # Country input
            self.country_input = QComboBox()
            # Only include US and Canada with full names
            self.country_input.addItem("United States", "US")
            self.country_input.addItem("Canada", "CA")
            # Set default to United States
            self.country_input.setCurrentIndex(0)
            self.form_layout.addRow("Country:", self.country_input)
            
            # Postal code input
            self.postal_input = QLineEdit()
            self.postal_input.setPlaceholderText("Enter postal/zip code")
            self.form_layout.addRow("Postal/Zip Code:", self.postal_input)
            
        elif location_type == 2:  # City
            # Country input
            self.country_input = QComboBox()
            # Only include US and Canada with full names
            self.country_input.addItem("United States", "US")
            self.country_input.addItem("Canada", "CA")
            # Set default to United States
            self.country_input.setCurrentIndex(0)
            self.form_layout.addRow("Country:", self.country_input)
            
            # State/Province input
            self.state_input = QLineEdit()
            self.state_input.setPlaceholderText("State/Province (optional)")
            self.form_layout.addRow("State/Province:", self.state_input)
            
            # City input
            self.city_input = QLineEdit()
            self.city_input.setPlaceholderText("Enter city name")
            self.form_layout.addRow("City:", self.city_input)
        
        # Re-add the min square footage and radius inputs with preserved values
        self.sqft_input = QSpinBox()
        self.sqft_input.setRange(0, 1000000)
        self.sqft_input.setSingleStep(1000)
        self.sqft_input.setValue(current_sqft)
        self.form_layout.addRow("Min Sq-Ft:", self.sqft_input)
        
        # Get current distance unit
        distance_unit = self.settings.value("distance_unit", "km")
        unit_display = {"km": "kilometers", "mi": "miles", "m": "meters"}
        unit_label = unit_display.get(distance_unit, "kilometers")
        
        # Radius input - use QDoubleSpinBox for decimal values
        if distance_unit == "km" or distance_unit == "mi":
            # For km and miles, we need decimal values
            self.radius_input = QDoubleSpinBox()
            if distance_unit == "km":
                self.radius_input.setRange(0.1, 10)
                self.radius_input.setValue(1.0 if current_radius <= 500 else 5.0)  # Default to 1km or 5km
            else:  # miles
                self.radius_input.setRange(0.1, 6)
                self.radius_input.setValue(0.6 if current_radius <= 500 else 3.0)  # Default to 0.6mi or 3mi
            self.radius_input.setSingleStep(0.1)
            self.radius_input.setDecimals(1)
        else:  # meters
            # For meters, we can use integer values
            self.radius_input = QSpinBox()
            self.radius_input.setRange(100, 10000)
            self.radius_input.setSingleStep(100)
            self.radius_input.setValue(current_radius)
        
        self.form_layout.addRow(f"Radius ({unit_label}):", self.radius_input)
    
    def get_coordinates(self):
        """Get coordinates based on current location type"""
        location_type = self.settings.value("location_type", 0, int)
        
        if location_type == 0:  # Coordinates
            return self.longitude_input.value(), self.latitude_input.value()
            
        elif location_type == 1:  # Postal/Zip Code
            # Get country code from userData (not display text)
            country = self.country_input.currentData()
            postal_code = self.postal_input.text().strip()
            
            if not postal_code:
                raise ValueError("Please enter a postal/zip code")
            
            # Try pgeocode first (faster)
            try:
                nomi = pgeocode.Nominatim(country)
                result = nomi.query_postal_code(postal_code)
                
                # Check if pgeocode found valid coordinates
                if not pd.isna(result['latitude']) and not pd.isna(result['longitude']):
                    self.status_label.setText("Using pgeocode result")
                    return result['longitude'], result['latitude']
                    
                # If pgeocode failed, try Nominatim as fallback
                self.status_label.setText("pgeocode failed, trying Nominatim...")
            except Exception as e:
                self.status_label.setText(f"pgeocode error: {str(e)}, trying Nominatim...")
            
            # Fallback to Nominatim
            try:
                geolocator = Nominatim(user_agent="BuildingSizeFinder")
                country_name = self.country_input.currentText()
                query = f"{postal_code}, {country_name}"
                location = geolocator.geocode(query)
                
                if not location:
                    raise ValueError(f"Could not find coordinates for postal code {postal_code}")
                
                self.status_label.setText("Using Nominatim result")
                return location.longitude, location.latitude
            except Exception as e:
                raise ValueError(f"Error geocoding postal code: {str(e)}")
            
        elif location_type == 2:  # City
            # Get full country name for query
            country_name = self.country_input.currentText()
            state = self.state_input.text().strip()
            city = self.city_input.text().strip()
            
            if not city:
                raise ValueError("Please enter a city name")
            
            # Build the location query
            location_query = city
            if state:
                location_query += f", {state}"
            location_query += f", {country_name}"
            
            # Get coordinates using Nominatim
            try:
                geolocator = Nominatim(user_agent="BuildingSizeFinder")
                location = geolocator.geocode(location_query)
                
                if not location:
                    raise ValueError(f"Could not find coordinates for {location_query}")
                
                return location.longitude, location.latitude
            except Exception as e:
                raise ValueError(f"Error geocoding city: {str(e)}")
    
    def start_search(self):
        """Start the building search"""
        try:
            # Get the search parameters
            longitude, latitude = self.get_coordinates()
            min_sqft = self.sqft_input.value()
            radius_value = self.radius_input.value()
            
            # Convert radius to meters based on selected unit
            distance_unit = self.settings.value("distance_unit", "km")
            if distance_unit == "km":
                radius_in_meters = int(radius_value * 1000)  # km to meters
            elif distance_unit == "mi":
                radius_in_meters = int(radius_value * 1609.34)  # miles to meters
            else:
                radius_in_meters = radius_value  # already in meters
            
            # Disable search button to prevent multiple searches
            self.search_button.setEnabled(False)
            self.progress_bar.show()
            
            # Clear previous results
            self.results_table.setRowCount(0)
            self.results_count.setText("Searching...")
            
            # Create and start worker thread
            self.worker = BuildingSearchWorker(longitude, latitude, min_sqft, radius_in_meters)
            self.worker.finished.connect(self.handle_results)
            self.worker.progress.connect(self.update_progress)
            self.worker.start()
            
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error: {str(e)}")
    
    @Slot(str)
    def update_progress(self, message):
        """Update the status message during search"""
        self.status_label.setText(message)
    
    @Slot(dict)
    def handle_results(self, result):
        """Handle the search results"""
        # Hide progress indicators
        self.progress_bar.hide()
        self.search_button.setEnabled(True)
        
        # Check for errors
        if "error" in result:
            self.status_label.setText(f"Error: {result['error']}")
            self.results_count.setText("Search failed")
            QMessageBox.critical(self, "Error", f"Search failed: {result['error']}")
            return
        
        # Update status
        buildings = result.get("buildings", [])
        total = result.get("total_buildings", 0)
        self.status_label.setText("Search completed")
        self.results_count.setText(f"Found {total} buildings")
        
        # Populate table
        self.results_table.setRowCount(total)
        
        for row, building in enumerate(buildings):
            # ID
            id_item = QTableWidgetItem(str(building["id"]))
            self.results_table.setItem(row, self.column_indexes["id"], id_item)
            
            # Square Footage
            sqft_item = QTableWidgetItem(f"{building['sqft']:,}")
            sqft_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.results_table.setItem(row, self.column_indexes["sqft"], sqft_item)
            
            # Levels (new column)
            levels_item = QTableWidgetItem(str(building.get("levels", "unknown")))
            levels_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.results_table.setItem(row, self.column_indexes["levels"], levels_item)
            
            # Latitude (now column 3 instead of 2)
            lat_item = QTableWidgetItem(f"{building['lat']:.6f}")
            lat_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.results_table.setItem(row, self.column_indexes["latitude"], lat_item)
            
            # Longitude (now column 4 instead of 3)
            lon_item = QTableWidgetItem(f"{building['lon']:.6f}")
            lon_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.results_table.setItem(row, self.column_indexes["longitude"], lon_item)
            
            # Address (now column 5 instead of 4)
            address_item = QTableWidgetItem(building.get("address", ""))
            self.results_table.setItem(row, self.column_indexes["address"], address_item)
            
            # Building Type (now column 6 instead of 5)
            type_item = QTableWidgetItem(str(building.get("building_type", "unknown")))
            self.results_table.setItem(row, self.column_indexes["type"], type_item)
            
            # Usage (new column 7)
            usage_item = QTableWidgetItem(building.get("usage", ""))
            self.results_table.setItem(row, self.column_indexes["usage"], usage_item)
            
            # Name (now column 8 instead of 7)
            name_item = QTableWidgetItem(str(building.get("name", "unnamed")))
            self.results_table.setItem(row, self.column_indexes["name"], name_item)
            
            # Apply alternating row colors
            for col in range(9):  # Updated from 8 to 9 columns
                item = self.results_table.item(row, col)
                if row % 2 == 0:
                    item.setBackground(QColor("#353535"))  # Dark mode alternating color
                else:
                    item.setBackground(QColor("#2d2d2d"))  # Dark mode base color
        
        # Auto resize rows for better appearance
        self.results_table.resizeRowsToContents()

    def closeEvent(self, event):
        """Save window state and geometry when closing"""
        # Save window state and geometry
        self.settings.setValue("windowGeometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        # Accept the event and close
        event.accept()

    def handle_table_resize(self, event):
        """Handle table resize events"""
        # Call the parent implementation first
        super(self.results_table.__class__, self.results_table).resizeEvent(event)
        
        # Update column widths based on percentages
        self.update_column_widths()
        
        # Accept the event
        event.accept()

    def update_column_widths(self):
        """Update column widths based on percentages without triggering recursion"""
        # Calculate available width (accounting for vertical scrollbar if present)
        scrollbar_width = 0
        if self.results_table.verticalScrollBar().isVisible():
            scrollbar_width = self.results_table.verticalScrollBar().width()
        
        available_width = self.results_table.width() - scrollbar_width
        
        # Block signals to prevent recursive calls
        header = self.results_table.horizontalHeader()
        header.blockSignals(True)
        
        # Set column widths according to percentages
        for col, percentage in enumerate(self.column_percentages):
            width = int(available_width * percentage / 100)
            header.resizeSection(col, width)
        
        # Unblock signals
        header.blockSignals(False)

    def recalculate_column_widths(self, column, old_size, new_size):
        """Recalculate column percentages after manual resizing"""
        # Prevent processing during automatic resize
        if hasattr(self, 'is_auto_resizing') and self.is_auto_resizing:
            return
        
        # Calculate total width
        total_width = 0
        header = self.results_table.horizontalHeader()
        for col in range(self.results_table.columnCount()):
            total_width += header.sectionSize(col)
        
        # Recalculate percentages
        if total_width > 0:
            for col in range(self.results_table.columnCount()):
                self.column_percentages[col] = (header.sectionSize(col) / total_width) * 100

    def apply_column_visibility(self):
        """Apply column visibility settings from QSettings"""
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
        
        # Get the visibility for each column from settings
        for column_key, column_index in self.column_indexes.items():
            is_visible = self.settings.value(f"column_visible_{column_key}", 
                                            columns_default.get(column_key, True), 
                                            bool)
            self.results_table.setColumnHidden(column_index, not is_visible)
        
        # Update the percentages after changing visibility
        self.update_column_percentages()

    def update_column_percentages(self):
        """Update column percentages based on which columns are visible"""
        # Count visible columns
        visible_columns = []
        for i in range(self.results_table.columnCount()):
            if not self.results_table.isColumnHidden(i):
                visible_columns.append(i)
        
        # Skip if no columns are visible
        if not visible_columns:
            return
        
        # Distribute percentages based on content importance
        # Give more space to text-heavy columns
        content_weight = {
            0: 8,   # ID
            1: 10,  # Sq-Ft
            2: 7,   # Levels
            3: 11,  # Latitude
            4: 11,  # Longitude
            5: 22,  # Address
            6: 9,   # Type
            7: 12,  # Usage
            8: 10   # Name
        }
        
        # Calculate total weight of visible columns
        total_weight = sum(content_weight[i] for i in visible_columns)
        
        # Create new percentages list based on visible columns
        self.column_percentages = []
        for i in range(self.results_table.columnCount()):
            if i in visible_columns:
                # Calculate percentage based on weight
                percentage = (content_weight[i] / total_weight) * 100
                self.column_percentages.append(percentage)
            else:
                # Hidden column gets 0%
                self.column_percentages.append(0)
        
        # Update column widths with new percentages
        self.update_column_widths()

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for a consistent look across platforms
    
    window = BuildingSizeFinderApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
