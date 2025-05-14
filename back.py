# Import necessary libraries
from flask import Flask, request, jsonify  # Flask web framework components
from datetime import datetime  # For handling timestamps
from flask_cors import CORS  # For handling Cross-Origin Resource Sharing (CORS)

# Initialize Flask application
app = Flask(__name__)
# Enable CORS for all routes to allow frontend to communicate with this API
CORS(app)

# Data storage structures:

# Dictionary to store the latest data received from ESP32
esp_data = {
    "analog_input": 0,          # Analog input value from sensor
    "danger_level": 0,          # Calculated danger level (0-100)
    "timestamp": "",            # Last update timestamp
    "emergency": False,         # Emergency state flag
    "red_led": False,           # Red LED status
    "blue_led": False,          # Blue LED status
    "buzzer": False,            # Buzzer status
    "emergency_led": False,     # Emergency LED status
    "servo_open": False         # Servo motor open/close status
}

# Dictionary to store control commands from the dashboard
control_data = {
    "emergency_button": False,  # Emergency button state from dashboard
    "servo_open": False         # Servo control command from dashboard
}

# List to store system event logs (max 50 entries)
log_entries = []

# Route for ESP32 to update its sensor data and status
@app.route("/esp/update", methods=["POST"])
def update_esp():
    global esp_data  # Access the global esp_data dictionary

    # Get JSON data from the request
    data = request.json
    # Get current timestamp in formatted string
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update ESP data with new values from the request
    # Using .get() with defaults in case some fields are missing
    esp_data = {
        "analog_input": data.get("analog_input", 0),
        "danger_level": data.get("danger_level", 0),
        "emergency": data.get("emergency", False),
        "red_led": data.get("red_led", False),
        "blue_led": data.get("blue_led", False),
        "buzzer": data.get("buzzer", False),
        "emergency_led": data.get("emergency_led", False),
        "servo_open": data.get("servo_open", False),
        "timestamp": current_time
    }

    # Check if emergency state was included in the update
    if data.get("emergency") is not None:
        # Determine event message based on emergency state
        event = "EMERGENCY ACTIVATED" if data["emergency"] else "Emergency cleared"
        # Add log entry for this event
        log_entries.append({
            "event": event,
            "time": current_time,
            "danger_level": esp_data["danger_level"],
            "emergency": data["emergency"]
        })
        # Maintain log size (remove oldest entry if over 50)
        if len(log_entries) > 50:
            log_entries.pop(0)

    # Return success response
    return jsonify({"message": "ESP data received"})

# Route for ESP32 to report emergency button state changes
@app.route("/esp/emergency", methods=["POST"])
def esp_emergency():
    global esp_data, log_entries
    
    # Get JSON data from request
    data = request.json
    # Extract emergency state (default to False if not provided)
    emergency_state = data.get("emergency", False)
    # Update global ESP data
    esp_data["emergency"] = emergency_state
    
    # Create log entry for this event
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event = "PHYSICAL EMERGENCY BUTTON PRESSED" if emergency_state else "Physical emergency cleared"
    log_entries.append({
        "event": event,
        "time": current_time,
        "danger_level": esp_data["danger_level"],
        "emergency": emergency_state
    })
    # Maintain log size
    if len(log_entries) > 50:
        log_entries.pop(0)
    
    # Return success response
    return jsonify({"message": "Emergency state updated"})

# Route for dashboard (Flet app) to trigger emergency state
@app.route("/flet/emergency", methods=["POST"])
def flet_emergency():
    global control_data, log_entries
    
    # Get JSON data from request
    data = request.json
    # Extract emergency state
    emergency_state = data.get("emergency", False)
    # Update control data
    control_data["emergency_button"] = emergency_state
    
    # Create log entry
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event = "FLET EMERGENCY BUTTON PRESSED" if emergency_state else "Flet emergency cleared"
    log_entries.append({
        "event": event,
        "time": current_time,
        "danger_level": esp_data["danger_level"],
        "emergency": emergency_state
    })
    # Maintain log size
    if len(log_entries) > 50:
        log_entries.pop(0)
    
    # Return success response
    return jsonify({"message": "Emergency state updated"})

# Route for controlling the servo from dashboard
@app.route("/esp/servo", methods=["POST"])
def control_servo():
    global control_data, log_entries
    
    # Get JSON data from request
    data = request.json
    # Extract servo state
    servo_state = data.get("servo_open", False)
    # Update control data
    control_data["servo_open"] = servo_state
    
    # Create log entry
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event = "Servo opened" if servo_state else "Servo closed"
    log_entries.append({
        "event": event,
        "time": current_time,
        "danger_level": esp_data["danger_level"],
        "emergency": esp_data["emergency"]
    })
    # Maintain log size
    if len(log_entries) > 50:
        log_entries.pop(0)
    
    # Return success response
    return jsonify({"message": "Servo state updated"})

# Route for ESP32 to check current servo command status
@app.route("/esp/servo_status", methods=["GET"])
def get_servo_status():
    # Return current servo control state
    return jsonify({"servo_open": control_data["servo_open"]})

# Route for ESP32 to check all control commands
@app.route("/esp/control", methods=["GET"])
def control_esp():
    # Return all control data (emergency and servo states)
    return jsonify(control_data)

# Route for dashboard to get current system status and logs
@app.route("/dashboard", methods=["GET"])
def get_dashboard():
    # Return ESP data and the most recent 20 log entries
    return jsonify({
        "esp": esp_data,
        "logs": log_entries[-20:]  # Show last 20 entries
    })

# Main entry point
if __name__ == "__main__":
    # Run the Flask app on all network interfaces, port 5000, with debug mode
    app.run(host="0.0.0.0", port=5000, debug=True)