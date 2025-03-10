import sys
import os
import webbrowser  # Add this import for opening URLs
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
                              QHeaderView, QSpinBox, QDoubleSpinBox, QProgressBar, QMessageBox,
                              QSplitter, QGroupBox, QFormLayout, QToolBar, QComboBox, QSizePolicy, QDialog)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSettings, QSize
from PySide6.QtGui import QIcon, QFont, QColor, QAction, QPainter, QPixmap

# Import your building size function
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from buildings.getSize import get_buildings_by_size, process_large_area
from settings import SettingsWindow

# Import geocoding functions
import pgeocode
import time
from geopy.geocoders import Nominatim
import pandas as pd
from threading import Timer
from theme import ThemeWindow

class LocationLinkWidget(QWidget):
    """Custom widget that shows a location icon that opens Google Maps when clicked"""
    
    def __init__(self, latitude, longitude, accent_color, parent=None):
        super().__init__(parent)
        self.latitude = latitude
        self.longitude = longitude
        self.accent_color = accent_color
        
        # Create a layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)  # Reduce margins to make widget more compact
        layout.setAlignment(Qt.AlignCenter)  # Center the icon both horizontally and vertically
        
        # Create a label with the location icon
        self.icon_label = QLabel()
        self.update_icon()
        
        # Set smaller fixed size for the icon
        self.icon_label.setFixedSize(20, 20)  # Smaller icon (was 24x24)
        
        # Add to layout
        layout.addWidget(self.icon_label)
        
        # Set cursor to pointing hand when hovering
        self.setCursor(Qt.PointingHandCursor)
    
    def update_icon(self):
        """Update the icon with the current accent color"""
        # Load the SVG file
        pixmap = QPixmap("./svg/location.svg")
        
        # Create a painter to recolor the SVG
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(self.accent_color))
        painter.end()
        
        # Set the recolored icon to the label
        self.icon_label.setPixmap(pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))  # Smaller icon
    
    def update_accent_color(self, accent_color):
        """Update the widget with a new accent color"""
        self.accent_color = accent_color
        self.update_icon()
    
    def mousePressEvent(self, event):
        """Handle mouse click event to open Google Maps"""
        if event.button() == Qt.LeftButton:
            maps_url = f"https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}"
            webbrowser.open(maps_url)
        super().mousePressEvent(event)

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
        
        # Initialize missing_addresses list
        self.missing_addresses = []
        
        # Load settings
        self.settings = QSettings("BuildingSizeFinder", "BuildingSizeFinder")
        
        # Load theme colors
        self.load_theme_colors()
        
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
        
        # Create button layout for search and location buttons
        button_layout = QHBoxLayout()
        
        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.setFixedHeight(40)
        self.search_button.clicked.connect(self.start_search)
        # Add initial styling to search button to match theme
        self.search_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.accent_color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {self.accent_pressed};
            }}
        """)
        button_layout.addWidget(self.search_button)
        
        # Location button that opens Google Maps
        self.location_button = QPushButton()
        
        # Create a white icon by loading and coloring the SVG
        icon = QIcon("./svg/location.svg")
        
        # Set the white icon to the button
        self.location_button.setIcon(icon)
        self.location_button.setToolTip("Open location in Google Maps")
        self.location_button.clicked.connect(self.open_in_google_maps)
        self.location_button.setFixedSize(40, 40)
        self.location_button.setIconSize(QSize(24, 24))
        self.location_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.accent_color};
                border-radius: 20px;
                padding: 6px;
                color: white;
            }}
            QPushButton:hover {{
                background-color: {self.accent_hover};
            }}
        """)
        button_layout.addWidget(self.location_button)
        
        # Add the button layout to the main layout
        top_layout.addLayout(button_layout)
        
        # Status display (should appear below buttons now)
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
            "ID", "Sq-Ft", "Levels", "Latitude", "Longitude", "Address", "Type", "Name", "Map"
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
            "name": 7,
            "map": 8
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
    
    def load_theme_colors(self):
        """Load theme colors from settings"""
        # Load accent color (default to blue)
        self.accent_color = self.settings.value("theme/accent_color", "#4a86e8")
        self.accent_hover = self.settings.value("theme/accent_hover", "#5a96f8")
        self.accent_pressed = self.settings.value("theme/accent_pressed", "#3a76d8")
        
        # Update styles for any elements that use these colors
        self.update_styled_elements()
    
    def create_toolbar(self):
        """Create the toolbar with settings and theme icons"""
        toolbar = QToolBar("Settings")
        toolbar.setObjectName("settingsToolbar")
        toolbar.setIconSize(QSize(24, 24))
        
        # Create spacer to push icons to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # Create theme action
        theme_action = QAction(QIcon("./icons/theme.png"), "Theme", self)
        theme_action.triggered.connect(self.open_theme_window)
        
        # Create settings action
        settings_action = QAction(QIcon("./icons/settings.png"), "Settings", self)
        settings_action.triggered.connect(self.show_settings)
        
        # Add widgets to toolbar
        toolbar.addWidget(spacer)
        toolbar.addAction(theme_action)
        toolbar.addAction(settings_action)
        
        self.addToolBar(toolbar)
    
    def open_theme_window(self):
        """Open the theme settings window"""
        theme_window = ThemeWindow(self)
        theme_window.theme_changed.connect(self.on_theme_changed)
        theme_window.exec()
    
    def on_theme_changed(self):
        """Handle theme changes from the theme window"""
        self.load_theme_colors()
        
        # Update application stylesheet
        self.update_stylesheet()
        
        # Update any specific styled elements
        self.update_styled_elements()
        
        # If settings window is open, update its stylesheet too
        for child in self.findChildren(QDialog):
            if hasattr(child, 'apply_stylesheet'):
                child.apply_stylesheet()
    
    def update_stylesheet(self):
        """Update the application stylesheet with new theme colors"""
        # Apply the same stylesheet but with updated colors
        self.setStyleSheet(f"""
            /* Main application background */
            QMainWindow, QWidget {{
                background-color: #2d2d2d;
                color: #e0e0e0;
            }}
            
            /* Form elements */
            QLabel {{
                color: #e0e0e0;
                background-color: transparent;
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
            
            /* Input fields */
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: #3d3d3d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
                selection-background-color: {self.accent_color};
            }}
            
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left-width: 1px;
                border-left-color: #555555;
                border-left-style: solid;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }}
            
            QComboBox::down-arrow {{
                width: 10px;
                height: 10px;
                background: #e0e0e0;
            }}
            
            QComboBox QAbstractItemView {{
                border: 1px solid #555555;
                selection-background-color: {self.accent_color};
                background-color: #3d3d3d;
                color: #e0e0e0;
            }}
            
            /* Buttons */
            QPushButton {{
                background-color: {self.accent_color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: {self.accent_hover};
            }}
            
            QPushButton:pressed {{
                background-color: {self.accent_pressed};
            }}
            
            QPushButton:disabled {{
                background-color: #555555;
                color: #888888;
            }}
            
            /* Table styling */
            QTableWidget {{
                background-color: #2d2d2d;
                alternate-background-color: #353535;
                color: #e0e0e0;
                gridline-color: #555555;
                border: 1px solid #555555;
                border-radius: 3px;
            }}
            
            QTableWidget::item {{
                padding: 4px;
                border: none;
            }}
            
            QTableWidget::item:selected {{
                background-color: {self.accent_color};
                color: white;
            }}
            
            QHeaderView::section {{
                background-color: #3d3d3d;
                color: #e0e0e0;
                padding: 5px;
                border: 1px solid #555555;
                font-weight: bold;
            }}
            
            /* Scrollbars */
            QScrollBar:vertical, QScrollBar:horizontal {{
                background-color: #2d2d2d;
                border: none;
                width: 12px;
                height: 12px;
            }}
            
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
            }}
            
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
                background-color: #666666;
            }}
            
            /* Progress bar */
            QProgressBar {{
                border: 1px solid #555555;
                border-radius: 3px;
                background-color: #3d3d3d;
                text-align: center;
                color: #e0e0e0;
            }}
            
            QProgressBar::chunk {{
                background-color: {self.accent_color};
                width: 10px;
            }}
            
            /* Splitter */
            QSplitter::handle {{
                background-color: #555555;
            }}
            
            QSplitter::handle:horizontal {{
                width: 2px;
            }}
            
            QSplitter::handle:vertical {{
                height: 2px;
            }}
            
            /* Toolbar */
            QToolBar {{
                background-color: #333333;
                border: none;
                spacing: 3px;
            }}
            
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
                padding: 5px;
            }}
            
            QToolButton:hover {{
                background-color: #4a4a4a;
            }}
            
            QToolButton:pressed {{
                background-color: #555555;
            }}
        """)
    
    def update_styled_elements(self):
        """Update any individually styled elements"""
        # Update location button style if it exists
        if hasattr(self, 'location_button'):
            self.location_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.accent_color};
                    border-radius: 20px;
                    padding: 6px;
                    color: white;
                }}
                QPushButton:hover {{
                    background-color: {self.accent_hover};
                }}
            """)
        
        # Update search button style if it exists
        if hasattr(self, 'search_button'):
            self.search_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.accent_color};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {self.accent_hover};
                }}
                QPushButton:pressed {{
                    background-color: {self.accent_pressed};
                }}
            """)
        
        # Update map widgets in the table
        self.update_map_widgets()
    
    def update_map_widgets(self):
        """Update the color of map widgets in the results table"""
        if not hasattr(self, 'results_table'):
            return
        
        # Check if map column exists and update all map widgets
        if "map" in self.column_indexes:
            map_col = self.column_indexes["map"]
            for row in range(self.results_table.rowCount()):
                widget = self.results_table.cellWidget(row, map_col)
                if isinstance(widget, LocationLinkWidget):
                    widget.update_accent_color(self.accent_color)
    
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
            self.country_input.blockSignals(True)  # Block signals during setup
            
            # Only include US and Canada with full names
            self.country_input.addItem("United States", "US")
            self.country_input.addItem("Canada", "CA")
            
            # Get saved country code directly from settings
            saved_country = self.settings.value("selected_country", "US", str)
            
            # Print debug info
            print(f"Loading country selection: {saved_country}")
            
            # Set the selection based on saved country
            if saved_country == "CA":
                self.country_input.setCurrentIndex(1)
            else:
                self.country_input.setCurrentIndex(0)
                
            self.country_input.blockSignals(False)  # Unblock signals after setup
            
            # Connect signal to save country selection when changed
            self.country_input.currentIndexChanged.connect(self.save_country_selection)
            
            self.form_layout.addRow("Country:", self.country_input)
            
            # Postal code input
            self.postal_input = QLineEdit()
            self.postal_input.setPlaceholderText("Enter postal/zip code")
            self.form_layout.addRow("Postal/Zip Code:", self.postal_input)
            
        elif location_type == 2:  # City
            # Country input
            self.country_input = QComboBox()
            self.country_input.blockSignals(True)  # Block signals during setup
            
            # Only include US and Canada with full names
            self.country_input.addItem("United States", "US")
            self.country_input.addItem("Canada", "CA")
            
            # Get saved country code directly from settings
            saved_country = self.settings.value("selected_country", "US", str)
            
            # Print debug info
            print(f"Loading country selection: {saved_country}")
            
            # Set the selection based on saved country
            if saved_country == "CA":
                self.country_input.setCurrentIndex(1)
            else:
                self.country_input.setCurrentIndex(0)
                
            self.country_input.blockSignals(False)  # Unblock signals after setup
            
            # Connect signal to save country selection when changed
            self.country_input.currentIndexChanged.connect(self.save_country_selection)
            
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
        
        # Add the radius input directly (without the location button)
        self.form_layout.addRow(f"Radius ({unit_label}):", self.radius_input)
    
    def save_country_selection(self, index):
        """Save the selected country to settings"""
        country_code = self.country_input.itemData(index)
        
        # Print debug info
        print(f"Saving country selection: {country_code}, index: {index}")
        
        # Explicitly save as string
        self.settings.setValue("selected_country", str(country_code))
        self.settings.sync()
    
    def get_coordinates(self):
        """Get coordinates based on current location type"""
        location_type = self.settings.value("location_type", 0, int)
        
        if location_type == 0:  # Coordinates
            return self.longitude_input.value(), self.latitude_input.value()
            
        elif location_type == 1:  # Postal/Zip Code
            # Get country code directly from current index
            country_index = self.country_input.currentIndex()
            country = "US" if country_index == 0 else "CA"
            
            # Save country selection
            self.settings.setValue("selected_country", country)
            self.settings.sync()
            
            postal_code = self.postal_input.text().strip().upper()
            
            if not postal_code:
                raise ValueError("Please enter a postal/zip code")
            
            # Format Canadian postal codes correctly (add space if missing)
            if country == "CA" and len(postal_code) == 6 and " " not in postal_code:
                # Canadian format is "A1A 1A1" - insert space after 3rd character
                postal_code = postal_code[:3] + " " + postal_code[3:]
                self.status_label.setText(f"Formatted Canadian postal code to: {postal_code}")
            
            # Try pgeocode first (faster)
            try:
                nomi = pgeocode.Nominatim(country)
                result = nomi.query_postal_code(postal_code)
                
                # Check if pgeocode found valid coordinates
                if not pd.isna(result['latitude']) and not pd.isna(result['longitude']):
                    self.status_label.setText(f"Using pgeocode result for {country}")
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
            # FIXED: Get country code directly from current index to avoid type issues
            country_index = self.country_input.currentIndex()
            country_code = "US" if country_index == 0 else "CA"
            
            self.settings.setValue("selected_country", country_code)
            self.settings.sync()
            
            # Print for debugging
            print(f"Using country for city search: {country_code}")
            
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
        """Handle search results and update the UI"""
        self.search_button.setEnabled(True)
        self.progress_bar.hide()
        
        # Clear missing addresses list for new search
        self.missing_addresses = []
        
        if "error" in result:
            QMessageBox.warning(self, "Search Error", result["error"])
            self.results_count.setText("Error")
            self.status_label.setText("Search failed")
            return
        
        # Store the buildings data for additional processing
        self.buildings = result["buildings"]
        
        # Apply building type filters if any are set
        self.apply_building_type_filters()
        
        # Update result count
        self.results_count.setText(f"Found {len(self.buildings)} buildings")
        
        # Populate results table
        self.results_table.setRowCount(len(self.buildings))
        
        for row, building in enumerate(self.buildings):
            # ID
            id_item = QTableWidgetItem(str(building["id"]))
            self.results_table.setItem(row, self.column_indexes["id"], id_item)
            
            # Sq-Ft
            sqft_item = QTableWidgetItem(f"{building['sqft']:,}")
            self.results_table.setItem(row, self.column_indexes["sqft"], sqft_item)
            
            # Levels
            levels_item = QTableWidgetItem(str(building.get("levels", "unknown")))
            self.results_table.setItem(row, self.column_indexes["levels"], levels_item)
            
            # Latitude
            lat_item = QTableWidgetItem(str(building["lat"]))
            self.results_table.setItem(row, self.column_indexes["latitude"], lat_item)
            
            # Longitude
            lon_item = QTableWidgetItem(str(building["lon"]))
            self.results_table.setItem(row, self.column_indexes["longitude"], lon_item)
            
            # Address
            address = building.get("address", "No address data")
            address_item = QTableWidgetItem(str(address))
            self.results_table.setItem(row, self.column_indexes["address"], address_item)
            
            # Check if address is incomplete
            has_street = any(street_type in address for street_type in ["Street", "St ", "Avenue", "Ave ", "Road", "Rd ", "Drive", "Dr ", "Lane", "Ln ", "Boulevard", "Blvd", "Way", "Place", "Court", "Ct "])
            
            # Track buildings with missing addresses
            if not address or address == "No address data" or not has_street:
                self.missing_addresses.append({
                    "row": row,
                    "lat": building['lat'],
                    "lon": building['lon']
                })
            
            # Building Type
            type_item = QTableWidgetItem(str(building.get("building_type", "unknown")))
            self.results_table.setItem(row, self.column_indexes["type"], type_item)
            
            # Name
            name_item = QTableWidgetItem(str(building.get("name", "unnamed")))
            self.results_table.setItem(row, self.column_indexes["name"], name_item)
            
            # Map Link - create a widget with the location icon
            if building['lat'] and building['lon']:
                location_widget = LocationLinkWidget(building['lat'], building['lon'], self.accent_color)
                self.results_table.setCellWidget(row, self.column_indexes["map"], location_widget)
            
            # Apply alternating row colors
            for col in range(9):  # Updated for the new column count
                if col != self.column_indexes["map"]:  # Skip the widget column
                    item = self.results_table.item(row, col)
                    if item:  # Only set background if item exists
                        if row % 2 == 0:
                            item.setBackground(QColor("#353535"))  # Dark mode alternating color
                        else:
                            item.setBackground(QColor("#2d2d2d"))  # Dark mode base color
        
        # Auto resize rows for better appearance
        self.results_table.resizeRowsToContents()
        
        # If there are buildings with missing addresses and the setting is enabled, fetch them
        fetch_addresses = self.settings.value("fetch_missing_addresses", True, bool)
        
        # Debug the fetch condition
        print(f"Fetch addresses setting: {fetch_addresses}")
        print(f"Missing addresses count: {len(self.missing_addresses)}")
        
        if fetch_addresses and len(self.missing_addresses) > 0:
            self.status_label.setText(f"Finding addresses for {len(self.missing_addresses)} buildings...")
            # Use a small delay to allow UI to update before starting address fetching
            Timer(0.5, self.fetch_missing_addresses).start()
        else:
            if len(self.missing_addresses) > 50:
                self.status_label.setText(f"Too many missing addresses ({len(self.missing_addresses)}). Skipping fetch.")
            elif len(self.missing_addresses) == 0:
                self.status_label.setText("No addresses need to be fetched.")
            else:
                self.status_label.setText("Address fetching is disabled in settings.")
    
    def fetch_missing_addresses(self):
        """Fetch missing addresses in a background process with rate limiting"""
        if not self.missing_addresses:
            self.status_label.setText("All addresses retrieved")
            return
        
        # Get the next building with missing address
        building_info = self.missing_addresses.pop(0)
        
        # Set up geocoder
        geolocator = Nominatim(user_agent="BuildingLocator")
        
        try:
            # Reverse geocode with structured address format
            location = geolocator.reverse(
                f"{building_info['lat']}, {building_info['lon']}",
                exactly_one=True,
                addressdetails=True  # Request structured address details
            )
            
            if location:
                # Format the address to be consistent with initial results
                formatted_address = self.format_address(location)
                
                # Update the table
                address_item = QTableWidgetItem(formatted_address)
                self.results_table.setItem(building_info['row'], self.column_indexes["address"], address_item)
                
                # Update stored building data
                if hasattr(self, 'buildings') and building_info['row'] < len(self.buildings):
                    self.buildings[building_info['row']]['address'] = formatted_address
        except Exception as e:
            print(f"Error retrieving address: {e}")
        
        # Update status
        remaining = len(self.missing_addresses)
        self.status_label.setText(f"Finding addresses: {remaining} remaining...")
        
        # Schedule the next request with delay to respect rate limits (1 second)
        if remaining > 0:
            Timer(1.0, self.fetch_missing_addresses).start()
        else:
            self.status_label.setText("All addresses retrieved")

    def format_address(self, location):
        """Format address consistently from Nominatim location object"""
        if not location or not location.raw or 'address' not in location.raw:
            return "No address data"
        
        address_parts = []
        address_data = location.raw['address']
        
        # Building number and street
        building_number = address_data.get('house_number') or address_data.get('building')
        street = address_data.get('road') or address_data.get('street')
        
        if building_number and street:
            address_parts.append(f"{building_number} {street}")
        elif street:
            address_parts.append(street)
        
        # City/town
        city = (address_data.get('city') or address_data.get('town') or 
                address_data.get('village') or address_data.get('hamlet'))
        if city:
            address_parts.append(city)
        
        # State/province
        state = address_data.get('state') or address_data.get('province')
        if state:
            address_parts.append(state)
        
        # Postal code
        postcode = address_data.get('postcode')
        if postcode:
            address_parts.append(postcode)
        
        return ", ".join(address_parts) if address_parts else "No address data"

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
        
        # Set the map column to a fixed width
        if "map" in self.column_indexes:
            map_col = self.column_indexes["map"]
            if not self.results_table.isColumnHidden(map_col):
                header.setSectionResizeMode(map_col, QHeaderView.Fixed)
                header.resizeSection(map_col, 40)  # Increased width for map column (was 30px)
                available_width -= 40  # Subtract from available space for other columns
        
        # Account for a small buffer to prevent horizontal scrollbar
        available_width -= 2  # Small buffer to prevent horizontal scrollbar
        
        # Set column widths according to percentages for other columns
        for col, percentage in enumerate(self.column_percentages):
            if col != self.column_indexes.get("map") and percentage > 0:  # Skip map column and hidden columns
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
            "id": False,
            "sqft": True,
            "levels": False,  # Off by default
            "latitude": False,  # Off by default
            "longitude": False,  # Off by default
            "address": True,
            "type": True,
            "name": True,
            "map": True  # Turn on by default since we've added it
        }
        
        # Get the visibility for each column from settings
        for column_key, column_index in self.column_indexes.items():
            is_visible = self.settings.value(f"column_visible_{column_key}", 
                                            columns_default.get(column_key, True), 
                                            bool)
            self.results_table.setColumnHidden(column_index, not is_visible)
        
        # Set the map column resize mode to Fixed
        if "map" in self.column_indexes:
            map_col = self.column_indexes["map"]
            if not self.results_table.isColumnHidden(map_col):
                self.results_table.horizontalHeader().setSectionResizeMode(map_col, QHeaderView.Fixed)
                self.results_table.setColumnWidth(map_col, 40)  # Increased width (was 30px)
        
        # Update the percentages after changing visibility
        self.update_column_percentages()

    def update_column_percentages(self):
        """Update column percentages based on which columns are visible"""
        # Count visible columns
        visible_columns = []
        for i in range(self.results_table.columnCount()):
            if not self.results_table.isColumnHidden(i) and i != self.column_indexes.get("map"):
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
            7: 12,  # Name
            # Map column is handled separately with fixed width
        }
        
        # Calculate total weight of visible columns
        total_weight = sum(content_weight.get(i, 0) for i in visible_columns)
        
        # Create new percentages list based on visible columns
        self.column_percentages = []
        for i in range(self.results_table.columnCount()):
            if i in visible_columns:
                # Calculate percentage based on weight
                percentage = (content_weight.get(i, 0) / total_weight) * 100
                self.column_percentages.append(percentage)
            else:
                # Hidden column or map column gets 0%
                self.column_percentages.append(0)
        
        # Update column widths with new percentages
        self.update_column_widths()

    def open_in_google_maps(self):
        """Open the current location in Google Maps"""
        try:
            # Get coordinates from the current location inputs
            longitude, latitude = self.get_coordinates()
            
            # Create Google Maps URL using the API format
            maps_url = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
            
            # Open in web browser
            webbrowser.open(maps_url)
            
            self.status_label.setText("Opened location in Google Maps")
        except Exception as e:
            QMessageBox.warning(self, "Location Error", f"Could not open maps: {str(e)}")

    def change_location_type(self, type_index):
        """Change the location input type and update the UI"""
        # FIXED: Save current values including current country selection
        if hasattr(self, 'country_input'):
            country_index = self.country_input.currentIndex()
            country_code = "US" if country_index == 0 else "CA"
            self.settings.setValue("selected_country", country_code)
            print(f"Saving country selection during type change: {country_code}")
        
        self.save_current_values()
        
        # Save the location type
        self.settings.setValue("location_type", type_index)
        self.settings.sync()
        
        # Update the UI
        self.create_location_inputs()

    def apply_building_type_filters(self):
        """Filter out buildings based on type settings"""
        if not hasattr(self, 'buildings') or not self.buildings:
            return
        
        # Get excluded building types from settings
        excluded_types = []
        for type_key in ["residential", "commercial", "industrial", "retail", 
                         "office", "warehouse", "garage", "shed", "nan"]:
            if self.settings.value(f"exclude_building_type_{type_key}", False, bool):
                excluded_types.append(type_key)
        
        # If no types are excluded, return early
        if not excluded_types:
            return
        
        # Filter buildings
        filtered_buildings = []
        excluded_count = 0
        
        for building in self.buildings:
            building_type = str(building.get("building_type", "")).lower()
            
            # Special case for NaN/unknown/yes
            if (building_type in ["", "unknown", "nan", "none", "yes"] or building_type == "nan") and "nan" in excluded_types:
                excluded_count += 1
                continue
            
            # Check if this building type should be excluded
            exclude = False
            for excluded_type in excluded_types:
                if excluded_type != "nan" and excluded_type in building_type:
                    exclude = True
                    excluded_count += 1
                    break
            
            if not exclude:
                filtered_buildings.append(building)
        
        # Update buildings list
        self.buildings = filtered_buildings
        
        # Update status
        if excluded_count > 0:
            self.status_label.setText(f"Excluded {excluded_count} buildings based on type filters")

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for a consistent look across platforms
    
    window = BuildingSizeFinderApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
