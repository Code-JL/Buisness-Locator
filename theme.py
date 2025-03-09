from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QColorDialog, QGroupBox, QFormLayout)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QIcon, QColor

class ThemeWindow(QDialog):
    """Theme selection window for customizing application appearance"""
    
    # Signal to notify main window when theme changes
    theme_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Theme Settings")
        self.setMinimumSize(400, 300)
        self.setWindowIcon(QIcon("./icons/theme.png"))
        
        # Initialize QSettings
        self.qsettings = QSettings("BuildingSizeFinder", "BuildingSizeFinder")
        
        # Set up the UI
        self.setup_ui()
        
        # Load saved theme
        self.load_theme()
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        
        # Theme group
        theme_group = QGroupBox("Accent Color")
        theme_layout = QFormLayout()
        
        # Current color preview
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(100, 30)
        self.color_preview.setStyleSheet("border: 1px solid #555555; border-radius: 3px;")
        
        # Color picker button
        self.color_button = QPushButton("Change Color")
        self.color_button.clicked.connect(self.pick_color)
        
        # Reset to default button
        self.reset_button = QPushButton("Reset to Default")
        self.reset_button.clicked.connect(self.reset_to_default)
        
        # Add widgets to layout
        color_layout = QHBoxLayout()
        color_layout.addWidget(self.color_preview)
        color_layout.addWidget(self.color_button)
        
        theme_layout.addRow("Current Accent:", color_layout)
        theme_layout.addRow("", self.reset_button)
        
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # Information label
        info_label = QLabel("Changes will apply to the entire application after saving, including the Settings window and location button.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Add spacer
        layout.addStretch()
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_theme)
        
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
        """Apply dark mode stylesheet to the theme window"""
        # Get current accent color
        accent_color = self.qsettings.value("theme/accent_color", "#4a86e8")
        accent_hover = self.qsettings.value("theme/accent_hover", "#5a96f8")
        accent_pressed = self.qsettings.value("theme/accent_pressed", "#3a76d8")
        
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
        """)
    
    def load_theme(self):
        """Load theme settings from QSettings"""
        # Load accent color (default to blue)
        accent_color = self.qsettings.value("theme/accent_color", "#4a86e8")
        
        # Update color preview
        self.color_preview.setStyleSheet(f"background-color: {accent_color}; border: 1px solid #555555; border-radius: 3px;")
        
        # Store current color
        self.current_color = QColor(accent_color)
    
    def pick_color(self):
        """Open color picker dialog"""
        color = QColorDialog.getColor(self.current_color, self, "Select Accent Color")
        
        if color.isValid():
            # Update preview
            self.current_color = color
            hex_color = color.name()
            self.color_preview.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #555555; border-radius: 3px;")
    
    def reset_to_default(self):
        """Reset to default blue accent color"""
        default_color = QColor("#4a86e8")
        self.current_color = default_color
        self.color_preview.setStyleSheet(f"background-color: {default_color.name()}; border: 1px solid #555555; border-radius: 3px;")
    
    def save_theme(self):
        """Save theme settings to QSettings"""
        # Get hex color
        hex_color = self.current_color.name()
        
        # Calculate hover and pressed colors (slightly lighter and darker)
        hover_color = QColor(self.current_color)
        hover_color.setHsv(
            hover_color.hue(),
            min(hover_color.saturation() + 20, 255),
            min(hover_color.value() + 20, 255)
        )
        
        pressed_color = QColor(self.current_color)
        pressed_color.setHsv(
            pressed_color.hue(),
            min(pressed_color.saturation() + 10, 255),
            max(pressed_color.value() - 20, 0)
        )
        
        # Save colors
        self.qsettings.setValue("theme/accent_color", hex_color)
        self.qsettings.setValue("theme/accent_hover", hover_color.name())
        self.qsettings.setValue("theme/accent_pressed", pressed_color.name())
        
        # Emit signal to notify main window
        self.theme_changed.emit()
        
        # Close the dialog
        self.accept()
