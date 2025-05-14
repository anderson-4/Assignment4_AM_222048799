import flet as ft
import requests
import time
import threading
from datetime import datetime

SERVER_URL = "http://192.168.8.130:5000"

def main(page: ft.Page):
    page.title = "ESP32 Emergency System Dashboard"
    page.vertical_alignment = "center"
    page.horizontal_alignment = "center"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20

    # Danger Level Indicator
    danger_level = ft.Text("0%", size=50, weight="bold")
    danger_status = ft.Text("Normal", size=30, weight="bold")
    emergency_status = ft.Text("System Normal", size=20, weight="bold")

    # Danger Gauge
    danger_gauge = ft.Container(
        width=300,
        height=300,
        border_radius=150,
        alignment=ft.alignment.center,
        animate=ft.animation.Animation(500, "easeInOut"),
        bgcolor=ft.Colors.GREEN
    )

    # Emergency Button
    emergency_button = ft.ElevatedButton(
        "✅ SYSTEM NORMAL",
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.GREEN_700,
            color=ft.Colors.WHITE
        ),
        width=200,
        height=60
    )

    # Servo Control Button
    servo_button = ft.ElevatedButton(
        "🔒 Close Door",
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_700,
            color=ft.Colors.WHITE
        ),
        width=200,
        height=60
    )

    # Log Displays
    current_log_display = ft.Column(
        scroll="auto",
        height=200,
        spacing=5,
        expand=True
    )
    
    historical_log_display = ft.Column(
        scroll="auto",
        height=500,
        spacing=5,
        expand=True
    )

    # Status Indicators
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

    # ESP Status Text
    esp_status_text = ft.Text("Waiting for ESP32 data...")

    def update_danger_indicator(level, emergency):
        danger_level.value = f"{level}%"
        
        if emergency:
            danger_status.value = "EMERGENCY!"
            danger_gauge.bgcolor = ft.Colors.YELLOW
            emergency_status.value = "EMERGENCY MODE ACTIVE"
            emergency_button.style.bgcolor = ft.Colors.RED_700
            emergency_button.text = "🚨 EMERGENCY"
        elif level > 70:
            danger_status.value = "DANGER!"
            danger_gauge.bgcolor = ft.Colors.RED
            emergency_status.value = "System Normal"
            emergency_button.style.bgcolor = ft.Colors.GREEN_700
            emergency_button.text = "✅ SYSTEM NORMAL"
        elif level > 40:
            danger_status.value = "Warning"
            danger_gauge.bgcolor = ft.Colors.BLUE
            emergency_status.value = "System Normal"
            emergency_button.style.bgcolor = ft.colors.GREEN_700
            emergency_button.text = "✅ SYSTEM NORMAL"
        else:
            danger_status.value = "Normal"
            danger_gauge.bgcolor = ft.Colors.GREEN
            emergency_status.value = "System Normal"
            emergency_button.style.bgcolor = ft.Colors.GREEN_700
            emergency_button.text = "✅ SYSTEM NORMAL"

        page.update()

    def refresh_status():
        try:
            response = requests.get(f"{SERVER_URL}/dashboard")
            if response.status_code == 200:
                dashboard = response.json()
                esp_d = dashboard.get("esp", {})
                logs = dashboard.get("logs", [])

                # Update Indicators
                danger_lvl = esp_d.get("danger_level", 0)
                emergency = esp_d.get("emergency", False)
                update_danger_indicator(danger_lvl, emergency)

                # Update ESP Status Text
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

                # Update Servo Button
                if esp_d.get('servo_open', False):
                    servo_button.text = "🔓 Open Door"
                else:
                    servo_button.text = "🔒 Close Door"

                # Update Current Logs
                current_log_display.controls = []
                for log in reversed(logs[-10:]):
                    danger_lvl = log.get("danger_level", 0)
                    emergency = log.get("emergency", False)
                    
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

                # Update Historical Logs
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

        page.update()

    def emergency_click(e):
        try:
            current_text = emergency_button.text
            new_state = current_text == "✅ SYSTEM NORMAL"
            
            response = requests.post(
                f"{SERVER_URL}/flet/emergency", 
                json={"emergency": new_state}
            )
            
            if response.status_code == 200:
                if new_state:
                    emergency_button.text = "🚨 EMERGENCY"
                    emergency_button.style.bgcolor = ft.Colors.RED_700
                else:
                    emergency_button.text = "✅ SYSTEM NORMAL"
                    emergency_button.style.bgcolor = ft.Colors.GREEN_700
                page.update()
                
                refresh_status()
        except Exception as ex:
            print(f"Error sending emergency state: {ex}")
            esp_status_text.value = f"Error: {str(ex)}"
            page.update()

    def servo_click(e):
        try:
            current_text = servo_button.text
            new_state = "🔓 Open Door" if "Close" in current_text else "🔒 Close Door"
            
            response = requests.post(
                f"{SERVER_URL}/esp/servo", 
                json={"servo_open": "Open" in new_state}
            )
            
            if response.status_code == 200:
                servo_button.text = new_state
                page.update()
                
                refresh_status()
        except Exception as ex:
            print(f"Error sending servo state: {ex}")
            esp_status_text.value = f"Error: {str(ex)}"
            page.update()

    def auto_refresh():
        while True:
            refresh_status()
            time.sleep(0.5)

    # Event Handlers
    emergency_button.on_click = emergency_click
    servo_button.on_click = servo_click

    # Start Auto-Refresh Thread
    threading.Thread(target=auto_refresh, daemon=True).start()

    # Danger Gauge Content
    danger_gauge.content = ft.Column([danger_level, danger_status], alignment=ft.alignment.center)

    # Create Tabs
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
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
        expand=1
    )

    # Build UI
    page.add(tabs)

    # Initial Refresh
    refresh_status()

ft.app(target=main)