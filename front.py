import flet as ft
import requests
import time
import threading
from datetime import datetime

# Server URL where the ESP32 data is being served
SERVER_URL = "http://192.168.8.130:5000"

def main(page: ft.Page):
    # Page setup - configure basic properties of the application window
    page.title = "ESP32 Emergency System Dashboard"
    page.vertical_alignment = "center"  # Center content vertically
    page.horizontal_alignment = "center"  # Center content horizontally
    page.theme_mode = ft.ThemeMode.LIGHT  # Use light theme
    page.padding = 20  # Add padding around the content

    # Danger Level Indicator - shows the numeric danger percentage
    danger_level = ft.Text("0%", size=50, weight="bold")
    # Text showing the current status (Normal/Warning/Danger/Emergency)
    danger_status = ft.Text("Normal", size=30, weight="bold")
    # Text showing whether emergency mode is active
    emergency_status = ft.Text("System Normal", size=20, weight="bold")

    # Danger Gauge - visual representation of danger level
    danger_gauge = ft.Container(
        width=300,  # Fixed width
        height=300,  # Fixed height
        border_radius=150,  # Makes it circular (half of width/height)
        alignment=ft.alignment.center,  # Center content inside
        animate=ft.animation.Animation(500, "easeInOut"),  # Smooth color transitions
        bgcolor=ft.Colors.GREEN  # Default color (safe/green)
    )

    # Emergency Button - toggles emergency mode
    emergency_button = ft.ElevatedButton(
        "✅ SYSTEM NORMAL",
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.GREEN_700,  # Green background
            color=ft.Colors.WHITE  # White text
        ),
        width=200,  # Fixed width
        height=60  # Fixed height
    )

    # Servo Control Button - controls the door mechanism
    servo_button = ft.ElevatedButton(
        "🔒 Close Door",
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_700,  # Blue background
            color=ft.Colors.WHITE  # White text
        ),
        width=200,  # Fixed width
        height=60  # Fixed height
    )

    # Current Log Display - shows recent events (last 10)
    current_log_display = ft.Column(
        scroll="auto",  # Enable scrolling if content overflows
        height=200,  # Fixed height
        spacing=5,  # Space between log entries
        expand=True  # Expand to fill available space
    )
    
    # Historical Log Display - shows all recorded events
    historical_log_display = ft.Column(
        scroll="auto",  # Enable scrolling
        height=500,  # Larger fixed height
        spacing=5,  # Space between entries
        expand=True  # Expand to fill space
    )

    # Status Indicators - legend explaining the color coding
    status_indicators = ft.Column([
        ft.Row([ft.Container(width=20, height=20, border_radius=10, bgcolor=ft.Colors.RED_200), 
               ft.Text("High Danger")], spacing=5),
        ft.Row([ft.Container(width=20, height=20, border_radius=10, bgcolor=ft.Colors.BLUE_200), 
               ft.Text("Medium Danger")], spacing=5),
        ft.Row([ft.Icon(ft.icons.WARNING, color=ft.Colors.YELLOW), 
               ft.Text("Emergency Mode")], spacing=5),
        ft.Row([ft.Icon(ft.icons.DOOR_SLIDING, color=ft.Colors.BLUE), 
               ft.Text("Door Status")], spacing=5)
    ], spacing=10)

    # ESP Status Text - detailed status readout from ESP32
    esp_status_text = ft.Text("Waiting for ESP32 data...")

    # Function to update the danger indicator based on current level
    def update_danger_indicator(level, emergency):
        danger_level.value = f"{level}%"  # Update percentage display
        
        # Determine status based on danger level and emergency state
        if emergency:
            danger_status.value = "EMERGENCY!"
            danger_gauge.bgcolor = ft.Colors.YELLOW
            emergency_status.value = "EMERGENCY MODE ACTIVE"
            emergency_button.style.bgcolor = ft.Colors.RED_700
            emergency_button.text = "🚨 EMERGENCY"
        elif level > 70:  # High danger
            danger_status.value = "DANGER!"
            danger_gauge.bgcolor = ft.Colors.RED
            emergency_status.value = "System Normal"
            emergency_button.style.bgcolor = ft.Colors.GREEN_700
            emergency_button.text = "✅ SYSTEM NORMAL"
        elif level > 40:  # Medium danger
            danger_status.value = "Warning"
            danger_gauge.bgcolor = ft.Colors.BLUE
            emergency_status.value = "System Normal"
            emergency_button.style.bgcolor = ft.colors.GREEN_700
            emergency_button.text = "✅ SYSTEM NORMAL"
        else:  # Normal/safe
            danger_status.value = "Normal"
            danger_gauge.bgcolor = ft.Colors.GREEN
            emergency_status.value = "System Normal"
            emergency_button.style.bgcolor = ft.Colors.GREEN_700
            emergency_button.text = "✅ SYSTEM NORMAL"

        page.update()  # Refresh the UI

    # Function to refresh all status information from the server
    def refresh_status():
        try:
            # Fetch data from server
            response = requests.get(f"{SERVER_URL}/dashboard")
            if response.status_code == 200:
                dashboard = response.json()
                esp_d = dashboard.get("esp", {})  # ESP32 data
                logs = dashboard.get("logs", [])  # Event logs

                # Update danger indicators
                danger_lvl = esp_d.get("danger_level", 0)
                emergency = esp_d.get("emergency", False)
                update_danger_indicator(danger_lvl, emergency)

                # Update detailed status text
                esp_status_text.value = (
                    f"Potentiometer: {esp_d.get('analog_input', 0)}\n"
                    f"Danger Level: {danger_lvl}%\n"
                    f"Red LED: {'ON' if danger_lvl > 70 else 'OFF'}\n"
                    f"Blue LED: {'ON' if danger_lvl > 40 else 'OFF'}\n"
                    f"Buzzer: {'ON' if danger_lvl > 70 or emergency else 'OFF'}\n"
                    f"Emergency LED: {'ON' if emergency else 'OFF'}\n"
                    f"Door: {'OPEN' if esp_d.get('servo_open', False) else 'CLOSED'}\n"
                    f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                # Update servo button text based on current door state
                if esp_d.get('servo_open', False):
                    servo_button.text = "🔓 Open Door"
                else:
                    servo_button.text = "🔒 Close Door"

                # Update current logs (most recent 10 entries)
                current_log_display.controls = []
                for log in reversed(logs[-10:]):
                    danger_lvl = log.get("danger_level", 0)
                    emergency = log.get("emergency", False)
                    
                    # Color code based on danger level
                    log_color = ft.Colors.RED if danger_lvl > 70 else (
                        ft.colors.BLUE if danger_lvl > 40 else ft.Colors.GREEN
                    )
                    if emergency:
                        log_color = ft.Colors.YELLOW
                    
                    current_log_display.controls.append(
                        ft.Text(
                            f"{log.get('time', '')} - {log.get('event', '')} "
                            f"(Danger: {danger_lvl}%)",
                            color=log_color
                        )
                    )

                # Update historical logs (all entries)
                historical_log_display.controls = []
                for log in reversed(logs):
                    danger_lvl = log.get("danger_level", 0)
                    emergency = log.get("emergency", False)
                    
                    log_color = ft.Colors.RED if danger_lvl > 70 else (
                        ft.colors.BLUE if danger_lvl > 40 else ft.Colors.GREEN
                    )
                    if emergency:
                        log_color = ft.Colors.YELLOW
                    
                    historical_log_display.controls.append(
                        ft.Text(
                            f"{log.get('time', '')} - {log.get('event', '')} "
                            f"(Danger: {danger_lvl}%)",
                            color=log_color
                        )
                    )

            else:
                esp_status_text.value = f"Error: {response.status_code}"
        except Exception as ex:
            esp_status_text.value = f"Exception: {str(ex)}"

        page.update()  # Refresh the UI

    # Emergency button click handler
    def emergency_click(e):
        try:
            current_text = emergency_button.text
            # Toggle emergency state (if button says "SYSTEM NORMAL", we're turning emergency ON)
            new_state = current_text == "✅ SYSTEM NORMAL"
            
            # Send command to server
            response = requests.post(
                f"{SERVER_URL}/flet/emergency", 
                json={"emergency": new_state}
            )
            
            if response.status_code == 200:
                # Update button appearance based on new state
                if new_state:
                    emergency_button.text = "🚨 EMERGENCY"
                    emergency_button.style.bgcolor = ft.Colors.RED_700
                else:
                    emergency_button.text = "✅ SYSTEM NORMAL"
                    emergency_button.style.bgcolor = ft.Colors.GREEN_700
                page.update()
                
                # Refresh all status information
                refresh_status()
        except Exception as ex:
            print(f"Error sending emergency state: {ex}")
            esp_status_text.value = f"Error: {str(ex)}"
            page.update()

    # Servo button click handler
    def servo_click(e):
        try:
            current_text = servo_button.text
            # Toggle door state (if button says "Close Door", we're opening it)
            new_state = "🔓 Open Door" if "Close" in current_text else "🔒 Close Door"
            
            # Send command to server
            response = requests.post(
                f"{SERVER_URL}/esp/servo", 
                json={"servo_open": "Open" in new_state}
            )
            
            if response.status_code == 200:
                servo_button.text = new_state
                page.update()
                
                # Refresh all status information
                refresh_status()
        except Exception as ex:
            print(f"Error sending servo state: {ex}")
            esp_status_text.value = f"Error: {str(ex)}"
            page.update()

    # Background thread function for automatic refresh
    def auto_refresh():
        while True:
            refresh_status()  # Refresh data
            time.sleep(0.5)  # Wait half second between refreshes

    # Attach event handlers to buttons
    emergency_button.on_click = emergency_click
    servo_button.on_click = servo_click

    # Start auto-refresh thread (runs in background)
    threading.Thread(target=auto_refresh, daemon=True).start()

    # Add content to the danger gauge container
    danger_gauge.content = ft.Column([danger_level, danger_status], alignment=ft.alignment.center)

    # Create tabbed interface
    tabs = ft.Tabs(
        selected_index=0,  # First tab selected by default
        animation_duration=300,  # Tab switch animation duration
        tabs=[
            # Dashboard tab
            ft.Tab(
                text="Dashboard",
                content=ft.Column(
                    [
                        ft.Text("ESP32 Emergency System", size=24, weight="bold"),
                        ft.Row([danger_gauge, status_indicators], alignment=ft.MainAxisAlignment.CENTER, spacing=40),
                        ft.Row([emergency_button, servo_button, emergency_status], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                        ft.Divider(),
                        ft.Text("System Status:", size=18, weight="bold"),
                        esp_status_text,
                        ft.Divider(),
                        ft.Text("Recent Events:", size=18, weight="bold"),
                        ft.Container(current_log_display, border=ft.border.all(1, ft.Colors.GREY_300), 
                                    padding=10, border_radius=5, width=600)
                    ],
                    spacing=20,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                )
            ),
            # Event log tab
            ft.Tab(
                text="Event Log",
                content=ft.Column(
                    [
                        ft.Text("Historical Event Log", size=24, weight="bold"),
                        ft.Container(historical_log_display, border=ft.border.all(1, ft.Colors.GREY_300), 
                                    padding=10, border_radius=5, width=600)
                    ],
                    spacing=20,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                )
            )
        ],
        expand=1  # Expand to fill available space
    )

    # Add tabs to the page
    page.add(tabs)

    # Initial data refresh
    refresh_status()

# Start the Flet application
ft.app(target=main)