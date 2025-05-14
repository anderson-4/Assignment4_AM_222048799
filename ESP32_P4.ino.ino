/*
 * ESP32 Emergency Monitoring System
 * 
 * This program monitors a potentiometer for danger levels, controls outputs based on thresholds,
 * handles emergency states, and communicates with a web server for remote monitoring and control.
 */

#include <WiFi.h>           // For WiFi connectivity
#include <HTTPClient.h>      // For making HTTP requests
#include <ArduinoJson.h>     // For JSON serialization/deserialization
#include <ESP32Servo.h>      // For servo motor control

// Configuration Section
const char* ssid = "HUAWEI_B535_26AE";       // WiFi SSID
const char* password = "YG9AA5BE3Q6";         // WiFi password
const char* server = "http://192.168.8.130:5000/esp/update";  // Server endpoint for data updates

// Pin Definitions
#define POTENTIOMETER_PIN 34    // Analog input for danger level
#define PUSHBUTTON_PIN 13       // Emergency button input
#define RED_LED_PIN 12          // High danger indicator
#define BLUE_LED_PIN 14         // Medium danger indicator
#define BUZZER_PIN 27           // Audible alarm
#define EMERGENCY_LED_PIN 33    // Visual emergency indicator
#define SERVO_PIN 15            // Servo motor control

// Thresholds for danger levels (0-100 scale)
#define MEDIUM_DANGER_THRESHOLD 55   // Threshold for medium danger (blue LED)
#define HIGH_DANGER_THRESHOLD 75     // Threshold for high danger (red LED + buzzer)

// Timing Constants (in milliseconds)
#define SEND_INTERVAL 2000           // How often to send data to server
#define WIFI_TIMEOUT 20000           // Max time to wait for WiFi connection
#define DEBOUNCE_DELAY 50            // Button debounce time
#define BUZZER_BLINK_INTERVAL 500    // Buzzer blink rate during high danger
#define EMERGENCY_CHECK_INTERVAL 1000 // How often to check server for emergency commands
#define SERVO_CHECK_INTERVAL 1000    // How often to check server for servo commands

// Global Variables
unsigned long lastSendTime = 0;          // Last time data was sent to server
unsigned long lastButtonChangeTime = 0;   // For button debouncing
unsigned long lastBuzzerToggle = 0;       // Last time buzzer was toggled
unsigned long lastEmergencyCheck = 0;     // Last time emergency status was checked
unsigned long lastServoCheck = 0;         // Last time servo status was checked
bool lastButtonState = HIGH;              // Previous button state (pull-up)
bool buttonStateChanged = false;          // Flag for button press detection
bool buzzerState = false;                 // Current buzzer state
bool currentButtonPressed = false;        // Current button state
bool emergencyState = false;              // Emergency mode status
bool servoState = false;                  // Current servo position (false=closed, true=open)
Servo myServo;                            // Servo object

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n\nESP32 Emergency System");

  // Initialize Pins
  pinMode(POTENTIOMETER_PIN, INPUT);
  pinMode(PUSHBUTTON_PIN, INPUT_PULLUP);  // Button uses internal pull-up resistor
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(BLUE_LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(EMERGENCY_LED_PIN, OUTPUT);

  // Initialize Servo
  myServo.attach(SERVO_PIN);
  myServo.write(0); // Start at 0 degrees (closed position)

  // Set initial states (all outputs off)
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(BLUE_LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(EMERGENCY_LED_PIN, LOW);

  // Test all outputs on startup
  testOutputs();
  
  // Connect to WiFi network
  connectToWiFi();
}

void loop() {
  unsigned long currentTime = millis();  // Get current time

  // Read sensors
  int potValue = readPotentiometer();    // Read analog value from potentiometer
  int dangerLevel = map(potValue, 0, 4095, 0, 100);  // Convert to 0-100 scale
  readButtonState();                    // Check emergency button state

  // Check for emergency commands from server periodically
  if (currentTime - lastEmergencyCheck >= EMERGENCY_CHECK_INTERVAL) {
    checkEmergencyStatus();
    lastEmergencyCheck = currentTime;
  }

  // Check for servo commands from server periodically
  if (currentTime - lastServoCheck >= SERVO_CHECK_INTERVAL) {
    checkServoStatus();
    lastServoCheck = currentTime;
  }

  // If button was pressed (with debounce), toggle emergency state
  if (buttonStateChanged && currentButtonPressed) {
    emergencyState = !emergencyState;             // Toggle emergency state
    updateEmergencyOutputs();                     // Update outputs accordingly
    sendEmergencyStateToServer();                 // Notify server
    buttonStateChanged = false;                   // Reset flag
  }

  // Control outputs based on danger level (unless in emergency mode)
  controlOutputs(dangerLevel, currentTime);

  // Send data to server at regular intervals
  if (currentTime - lastSendTime >= SEND_INTERVAL) {
    if (WiFi.status() == WL_CONNECTED) {
      sendSensorData(potValue, dangerLevel, emergencyState);
    } else {
      Serial.println("WiFi disconnected. Attempting to reconnect...");
      connectToWiFi();  // Try to reconnect if connection lost
    }
    lastSendTime = currentTime;
  }

  delay(10);  // Small delay to prevent watchdog timer issues
}

/**
 * Updates all outputs when emergency state changes
 */
void updateEmergencyOutputs() {
  // Set emergency LED according to state
  digitalWrite(EMERGENCY_LED_PIN, emergencyState ? HIGH : LOW);
  // Set buzzer according to state (continuous in emergency)
  digitalWrite(BUZZER_PIN, emergencyState ? HIGH : LOW);
  
  // Close servo during emergency (safety measure)
  if (emergencyState) {
    controlServo(false);
  }
}

/**
 * Controls the servo motor position
 * @param open - true to open (90°), false to close (0°)
 */
void controlServo(bool open) {
  if (open) {
    myServo.write(90);  // Move to 90 degrees (open position)
    servoState = true;
  } else {
    myServo.write(0);   // Return to 0 degrees (closed position)
    servoState = false;
  }
}

/**
 * Sends the current emergency state to the server
 */
void sendEmergencyStateToServer() {
  // Skip if not connected to WiFi
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin("http://192.168.8.130:5000/esp/emergency");
  http.addHeader("Content-Type", "application/json");

  // Create JSON payload
  DynamicJsonDocument doc(128);
  doc["emergency"] = emergencyState;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  // Send POST request
  int httpCode = http.POST(jsonPayload);
  
  // Process response
  if (httpCode > 0) {
    if (httpCode == HTTP_CODE_OK) {
      String response = http.getString();
      Serial.println("Server response: " + response);
    }
  } else {
    Serial.printf("HTTP error: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();  // Free resources
}

/**
 * Connects to WiFi network with timeout and visual feedback
 */
void connectToWiFi() {
  Serial.println("Connecting to WiFi...");
  WiFi.mode(WIFI_STA);        // Set as station (client)
  WiFi.disconnect();          // Ensure we're not connected
  delay(100);
  WiFi.begin(ssid, password); // Start connection

  unsigned long startAttemptTime = millis();
  bool ledState = false;

  // Attempt connection with timeout
  while (WiFi.status() != WL_CONNECTED && millis() - startAttemptTime < WIFI_TIMEOUT) {
    Serial.print(".");
    ledState = !ledState;                   // Toggle LED state
    digitalWrite(BLUE_LED_PIN, ledState);   // Visual feedback
    delay(500);
  }

  // Handle connection failure
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nFailed to connect to WiFi");
    // Blink blue LED rapidly to indicate failure
    for (int i = 0; i < 10; i++) {
      digitalWrite(BLUE_LED_PIN, HIGH);
      delay(200);
      digitalWrite(BLUE_LED_PIN, LOW);
      delay(200);
    }
    ESP.restart();  // Restart ESP (could implement retry logic instead)
  } else {
    // Connection successful
    Serial.println("\nConnected to WiFi");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    digitalWrite(BLUE_LED_PIN, LOW);  // Turn off connection indicator
  }
}

/**
 * Checks server for emergency commands
 */
void checkEmergencyStatus() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin("http://192.168.8.130:5000/esp/control");
  int httpCode = http.GET();

  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    DynamicJsonDocument doc(128);
    deserializeJson(doc, payload);

    // Get emergency state from server
    bool serverEmergencyState = doc["emergency_button"];
    
    // Update local state if different from server
    if (serverEmergencyState != emergencyState) {
      emergencyState = serverEmergencyState;
      updateEmergencyOutputs();
    }
  }
  http.end();
}

/**
 * Checks server for servo commands
 */
void checkServoStatus() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin("http://192.168.8.130:5000/esp/servo_status");
  int httpCode = http.GET();

  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    DynamicJsonDocument doc(128);
    deserializeJson(doc, payload);

    // Get servo state from server
    bool serverServoState = doc["servo_open"];
    
    // Update servo if state changed and not in emergency
    if (serverServoState != servoState && !emergencyState) {
      controlServo(serverServoState);
    }
  }
  http.end();
}

/**
 * Reads potentiometer value with averaging to reduce noise
 * @return Averaged analog reading (0-4095)
 */
int readPotentiometer() {
  int samples = 5;  // Number of samples to average
  int sum = 0;
  
  for (int i = 0; i < samples; i++) {
    sum += analogRead(POTENTIOMETER_PIN);
    delay(10);  // Small delay between samples
  }
  return sum / samples;  // Return average
}

/**
 * Reads button state with debouncing
 */
void readButtonState() {
  bool currentState = digitalRead(PUSHBUTTON_PIN);

  // If state changed, record time
  if (currentState != lastButtonState) {
    lastButtonChangeTime = millis();
  }

  // Only consider state change if stable for debounce period
  if ((millis() - lastButtonChangeTime) > DEBOUNCE_DELAY) {
    if (currentState != lastButtonState) {
      lastButtonState = currentState;
      currentButtonPressed = (currentState == HIGH);  // HIGH because of pull-up
      
      // Only trigger on button press (not release)
      if (currentButtonPressed) {
        buttonStateChanged = true;
        Serial.println("Button pressed!");
      }
    }
  }
}

/**
 * Tests all outputs on startup
 */
void testOutputs() {
  Serial.println("Testing outputs...");
  
  // Test each output in sequence
  digitalWrite(RED_LED_PIN, HIGH);
  delay(500);
  digitalWrite(BLUE_LED_PIN, HIGH);
  delay(500);
  digitalWrite(BUZZER_PIN, HIGH);
  delay(500);
  digitalWrite(EMERGENCY_LED_PIN, HIGH);
  delay(500);
  
  // Test servo (open and close)
  controlServo(true);
  delay(1000);
  controlServo(false);
  delay(500);
  
  // Turn all outputs off
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(BLUE_LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(EMERGENCY_LED_PIN, LOW);
  
  Serial.println("Output test complete");
}

/**
 * Controls outputs based on danger level and current time
 * @param dangerLevel - Current danger level (0-100)
 * @param currentTime - Current time from millis()
 */
void controlOutputs(int dangerLevel, unsigned long currentTime) {
  // Emergency mode overrides normal operation
  if (emergencyState) {
    digitalWrite(RED_LED_PIN, HIGH);  // Red LED on in emergency
    digitalWrite(BLUE_LED_PIN, LOW);
    return;
  }

  // High danger level (red LED + blinking buzzer)
  if (dangerLevel > HIGH_DANGER_THRESHOLD) {
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(BLUE_LED_PIN, LOW);
    
    // Toggle buzzer at set interval
    if (currentTime - lastBuzzerToggle >= BUZZER_BLINK_INTERVAL) {
      buzzerState = !buzzerState;
      digitalWrite(BUZZER_PIN, buzzerState);
      lastBuzzerToggle = currentTime;
    }
  } 
  // Medium danger level (blue LED only)
  else if (dangerLevel > MEDIUM_DANGER_THRESHOLD) {
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(BLUE_LED_PIN, HIGH);
    digitalWrite(BUZZER_PIN, LOW);
    buzzerState = false;  // Ensure buzzer is off
  } 
  // Normal operation (all outputs off)
  else {
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(BLUE_LED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    buzzerState = false;
  }
}

/**
 * Sends sensor data and system state to server
 * @param potValue - Raw potentiometer value
 * @param dangerLevel - Calculated danger level (0-100)
 * @param emergency - Current emergency state
 */
void sendSensorData(int potValue, int dangerLevel, bool emergency) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(server);
  http.addHeader("Content-Type", "application/json");

  // Create JSON payload with all relevant data
  DynamicJsonDocument doc(256);
  doc["analog_input"] = potValue;
  doc["danger_level"] = dangerLevel;
  doc["emergency"] = emergency;
  doc["red_led"] = digitalRead(RED_LED_PIN);
  doc["blue_led"] = digitalRead(BLUE_LED_PIN);
  doc["buzzer"] = digitalRead(BUZZER_PIN);
  doc["emergency_led"] = digitalRead(EMERGENCY_LED_PIN);
  doc["servo_open"] = servoState;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  Serial.print("Sending data: ");
  Serial.println(jsonPayload);

  // Send POST request
  int httpCode = http.POST(jsonPayload);
  
  // Process response
  if (httpCode > 0) {
    if (httpCode == HTTP_CODE_OK) {
      String response = http.getString();
      Serial.println("Server response: " + response);
    }
  } else {
    Serial.printf("HTTP error: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();  // Free resources
}