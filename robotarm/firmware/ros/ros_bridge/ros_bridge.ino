/*
 * PhantomX Reactor - ROS 2 Serial Bridge
 * 
 * This sketch bridges ROS 2 commands (via serial) to AX-12 servos.
 * 
 * Protocol:
 *   Commands are ASCII strings terminated by newline
 *   Format: COMMAND [ARGS...]
 *   
 * Commands:
 *   POS <j1> <j2> <j3> <j4> <j5> <j6> <j7> <j8>
 *     Set joint positions (0-1023 for each servo)
 *   
 *   GET
 *     Get current joint positions
 *     Response: JOINTS <p1> <p2> ... <p8>
 *   
 *   PING
 *     Check connection
 *     Response: PONG
 *   
 *   TORQUE <0|1>
 *     Enable/disable torque on all servos
 *   
 *   SERVO_TORQUE <id> <0|1>
 *     Enable/disable torque on specific servo
 *   
 *   BAUD <rate>
 *     Set serial baud rate (default: 115200)
 *
 * Servo Mapping:
 *   ID 1: Base
 *   ID 2,3: Shoulder (dual, mirrored)
 *   ID 4,5: Elbow (dual, mirrored)
 *   ID 6: Wrist tilt
 *   ID 7: Wrist rotation
 *   ID 8: Gripper
 */

#include <ax12.h>

// Servo IDs
#define NUM_SERVOS 8
const byte SERVO_IDS[NUM_SERVOS] = {1, 2, 3, 4, 5, 6, 7, 8};

// AX-12 registers
#define AX_TORQUE_ENABLE 24
#define AX_PRESENT_POS_L 36
#define AX_GOAL_POS_L 30

// Input buffer
#define MAX_CMD_LEN 128
char cmdBuffer[MAX_CMD_LEN];
int cmdIndex = 0;

void setup() {
    // Default to 115200 for ROS 2 serial communication
    Serial.begin(115200);
    
    delay(2000);
    
    // Initialize AX-12 at 1Mbps
    ax12Init(1000000);
    
    // Signal ready
    Serial.println("READY");
}

void loop() {
    // Read serial input
    while (Serial.available()) {
        char c = Serial.read();
        
        if (c == '\n' || c == '\r') {
            if (cmdIndex > 0) {
                cmdBuffer[cmdIndex] = '\0';
                processCommand(cmdBuffer);
                cmdIndex = 0;
            }
        } else {
            if (cmdIndex < MAX_CMD_LEN - 1) {
                cmdBuffer[cmdIndex++] = c;
            }
        }
    }
}

void processCommand(char* cmd) {
    // Parse command word
    char* token = strtok(cmd, " ");
    if (!token) return;
    
    if (strcmp(token, "POS") == 0) {
        handleSetPositions();
    } else if (strcmp(token, "GET") == 0) {
        handleGetPositions();
    } else if (strcmp(token, "PING") == 0) {
        Serial.println("PONG");
    } else if (strcmp(token, "TORQUE") == 0) {
        handleTorque(true);
    } else if (strcmp(token, "SERVO_TORQUE") == 0) {
        handleServoTorque();
    } else if (strcmp(token, "BAUD") == 0) {
        handleBaud();
    } else {
        Serial.print("ERROR: Unknown command '");
        Serial.print(token);
        Serial.println("'");
    }
}

void handleSetPositions() {
    int positions[NUM_SERVOS];
    
    // Read 8 position values
    for (int i = 0; i < NUM_SERVOS; i++) {
        char* token = strtok(NULL, " ");
        if (!token) {
            Serial.println("ERROR: Expected 8 positions");
            return;
        }
        positions[i] = atoi(token);
        
        // Validate range
        if (positions[i] < 0 || positions[i] > 1023) {
            Serial.print("ERROR: Position ");
            Serial.print(i+1);
            Serial.println(" out of range (0-1023)");
            return;
        }
    }
    
    // Send commands to servos
    // Note: Servos 2&3 and 4&5 need mirroring
    ax12SetRegister2(SERVO_IDS[0], AX_GOAL_POS_L, positions[0]);  // Base
    
    // Shoulder (mirrored)
    ax12SetRegister2(SERVO_IDS[1], AX_GOAL_POS_L, positions[1]);
    ax12SetRegister2(SERVO_IDS[2], AX_GOAL_POS_L, 1023 - positions[1]);
    
    // Elbow (mirrored)
    ax12SetRegister2(SERVO_IDS[3], AX_GOAL_POS_L, positions[3]);
    ax12SetRegister2(SERVO_IDS[4], AX_GOAL_POS_L, 1023 - positions[3]);
    
    ax12SetRegister2(SERVO_IDS[5], AX_GOAL_POS_L, positions[5]);  // Wrist tilt
    ax12SetRegister2(SERVO_IDS[6], AX_GOAL_POS_L, positions[6]);  // Wrist rot
    ax12SetRegister2(SERVO_IDS[7], AX_GOAL_POS_L, positions[7]);  // Gripper
    
    Serial.println("OK");
}

void handleGetPositions() {
    Serial.print("JOINTS");
    
    for (int i = 0; i < NUM_SERVOS; i++) {
        int pos = ax12GetRegister(SERVO_IDS[i], AX_PRESENT_POS_L, 2);
        if (pos == -1) {
            Serial.print(" -1");
        } else {
            Serial.print(" ");
            Serial.print(pos);
        }
    }
    Serial.println("");
}

void handleTorque(bool all) {
    char* token = strtok(NULL, " ");
    if (!token) {
        Serial.println("ERROR: Expected 0 or 1");
        return;
    }
    
    int enable = atoi(token);
    if (enable != 0 && enable != 1) {
        Serial.println("ERROR: Torque must be 0 or 1");
        return;
    }
    
    for (int i = 0; i < NUM_SERVOS; i++) {
        ax12SetRegister(SERVO_IDS[i], AX_TORQUE_ENABLE, enable);
        delay(10);
    }
    
    Serial.print("TORQUE ");
    Serial.println(enable ? "ON" : "OFF");
}

void handleServoTorque() {
    char* idToken = strtok(NULL, " ");
    char* valToken = strtok(NULL, " ");
    
    if (!idToken || !valToken) {
        Serial.println("ERROR: Usage: SERVO_TORQUE <id> <0|1>");
        return;
    }
    
    int id = atoi(idToken);
    int enable = atoi(valToken);
    
    if (id < 1 || id > 8) {
        Serial.println("ERROR: Invalid servo ID (1-8)");
        return;
    }
    
    if (enable != 0 && enable != 1) {
        Serial.println("ERROR: Torque must be 0 or 1");
        return;
    }
    
    ax12SetRegister(id, AX_TORQUE_ENABLE, enable);
    Serial.print("SERVO ");
    Serial.print(id);
    Serial.print(" TORQUE ");
    Serial.println(enable ? "ON" : "OFF");
}

void handleBaud() {
    char* token = strtok(NULL, " ");
    if (!token) {
        Serial.println("ERROR: Expected baud rate");
        return;
    }
    
    long baud = atol(token);
    
    // Valid standard rates
    if (baud != 9600 && baud != 19200 && baud != 38400 && 
        baud != 57600 && baud != 115200 && baud != 230400 &&
        baud != 460800 && baud != 500000 && baud != 1000000) {
        Serial.println("ERROR: Invalid baud rate");
        return;
    }
    
    Serial.print("Setting baud to ");
    Serial.println(baud);
    delay(100);
    Serial.end();
    Serial.begin(baud);
}
