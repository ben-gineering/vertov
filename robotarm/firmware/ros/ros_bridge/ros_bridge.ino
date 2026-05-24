/*
 * PhantomX Reactor - ROS 2 Serial Bridge
 * 
 * This sketch bridges ROS 2 commands (via serial) to AX-12 servos.
 * Matches Robotnik Automation's official URDF structure.
 * 
 * Protocol:
 *   Commands are ASCII strings terminated by newline
 *   Format: COMMAND [ARGS...]
 *   
 * Commands:
 *   POS <j1> <j2> <j3> <j4> <j5> <j6> <j7> <j8>
 *     Set servo positions (0-1023 for each servo)
 *     Note: ROS sends 6 joint values, this maps to 8 servos
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
 * Servo Mapping (matching official URDF):
 *   ID 1: shoulder_yaw_joint
 *   ID 2,3: shoulder_pitch_joint (dual, mirrored)
 *   ID 4,5: elbow_pitch_joint (dual, mirrored)
 *   ID 6: wrist_pitch_joint
 *   ID 7: wrist_roll_joint
 *   ID 8: gripper_revolute_joint
 *
 * Joint Order (ROS → Arduino):
 *   [0] shoulder_yaw (servo 1)
 *   [1] shoulder_pitch (servos 2,3 - auto-mirrored)
 *   [2] elbow_pitch (servos 4,5 - auto-mirrored)
 *   [3] wrist_pitch (servo 6)
 *   [4] wrist_roll (servo 7)
 *   [5] gripper (servo 8)
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
    // ROS sends 6 joint values, we map to 8 servos
    int rosPositions[6];
    
    // Read 6 position values from ROS
    for (int i = 0; i < 6; i++) {
        char* token = strtok(NULL, " ");
        if (!token) {
            Serial.println("ERROR: Expected 6 positions (ROS joints)");
            return;
        }
        rosPositions[i] = atoi(token);
        
        // Validate range
        if (rosPositions[i] < 0 || rosPositions[i] > 1023) {
            Serial.print("ERROR: Position ");
            Serial.print(i+1);
            Serial.println(" out of range (0-1023)");
            return;
        }
    }
    
    // Map 6 ROS joints to 8 physical servos
    // Joint order: shoulder_yaw, shoulder_pitch, elbow_pitch, wrist_pitch, wrist_roll, gripper
    ax12SetRegister2(1, AX_GOAL_POS_L, rosPositions[0]);  // shoulder_yaw
    
    // shoulder_pitch (dual servos, mirrored)
    ax12SetRegister2(2, AX_GOAL_POS_L, rosPositions[1]);
    ax12SetRegister2(3, AX_GOAL_POS_L, 1023 - rosPositions[1]);
    
    // elbow_pitch (dual servos, mirrored)
    ax12SetRegister2(4, AX_GOAL_POS_L, rosPositions[2]);
    ax12SetRegister2(5, AX_GOAL_POS_L, 1023 - rosPositions[2]);
    
    ax12SetRegister2(6, AX_GOAL_POS_L, rosPositions[3]);  // wrist_pitch
    ax12SetRegister2(7, AX_GOAL_POS_L, rosPositions[4]);  // wrist_roll
    ax12SetRegister2(8, AX_GOAL_POS_L, rosPositions[5]);  // gripper
    
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
