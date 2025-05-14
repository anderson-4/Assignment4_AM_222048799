from flask import Flask, request, jsonify
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Data storage
esp_data = {
    "analog_input": 0,
    "danger_level": 0,
    "timestamp": "",
    "emergency": False,
    "red_led": False,
    "blue_led": False,
    "buzzer": False,
    "emergency_led": False,
    "servo_open": False
}

control_data = {
    "emergency_button": False,
    "servo_open": False
}

log_entries = []

@app.route("/esp/update", methods=["POST"])
def update_esp():
    global esp_data

    data = request.json
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update ESP data
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

    # Log emergency state changes
    if data.get("emergency") is not None:
        event = "EMERGENCY ACTIVATED" if data["emergency"] else "Emergency cleared"
        log_entries.append({
            "event": event,
            "time": current_time,
            "danger_level": esp_data["danger_level"],
            "emergency": data["emergency"]
        })
        if len(log_entries) > 50:
            log_entries.pop(0)

    return jsonify({"message": "ESP data received"})

@app.route("/esp/emergency", methods=["POST"])
def esp_emergency():
    global esp_data, log_entries
    
    data = request.json
    emergency_state = data.get("emergency", False)
    esp_data["emergency"] = emergency_state
    
    # Log the emergency event
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event = "PHYSICAL EMERGENCY BUTTON PRESSED" if emergency_state else "Physical emergency cleared"
    log_entries.append({
        "event": event,
        "time": current_time,
        "danger_level": esp_data["danger_level"],
        "emergency": emergency_state
    })
    if len(log_entries) > 50:
        log_entries.pop(0)
    
    return jsonify({"message": "Emergency state updated"})

@app.route("/flet/emergency", methods=["POST"])
def flet_emergency():
    global control_data, log_entries
    
    data = request.json
    emergency_state = data.get("emergency", False)
    control_data["emergency_button"] = emergency_state
    
    # Log the emergency event
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event = "FLET EMERGENCY BUTTON PRESSED" if emergency_state else "Flet emergency cleared"
    log_entries.append({
        "event": event,
        "time": current_time,
        "danger_level": esp_data["danger_level"],
        "emergency": emergency_state
    })
    if len(log_entries) > 50:
        log_entries.pop(0)
    
    return jsonify({"message": "Emergency state updated"})

@app.route("/esp/servo", methods=["POST"])
def control_servo():
    global control_data, log_entries
    
    data = request.json
    servo_state = data.get("servo_open", False)
    control_data["servo_open"] = servo_state
    
    # Log the servo event
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event = "Servo opened" if servo_state else "Servo closed"
    log_entries.append({
        "event": event,
        "time": current_time,
        "danger_level": esp_data["danger_level"],
        "emergency": esp_data["emergency"]
    })
    if len(log_entries) > 50:
        log_entries.pop(0)
    
    return jsonify({"message": "Servo state updated"})

@app.route("/esp/servo_status", methods=["GET"])
def get_servo_status():
    return jsonify({"servo_open": control_data["servo_open"]})

@app.route("/esp/control", methods=["GET"])
def control_esp():
    return jsonify(control_data)

@app.route("/dashboard", methods=["GET"])
def get_dashboard():
    return jsonify({
        "esp": esp_data,
        "logs": log_entries[-20:]  # Show last 20 entries
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
    