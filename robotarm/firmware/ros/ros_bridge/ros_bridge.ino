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
 *   SPEED <0-1023>
 *     Set moving speed for all servos
 *     0 = max speed, 1023 = slowest
 *     Default: 300
 *   
 *   POS <j1> <j2> <j3> <j4> <j5> <j6> [speed]
 *     Set servo positions with optional speed override
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
#include <string.h>

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

// Moving speed for all servos (AX-12: 0=max speed, 1023=slowest)
// Default to moderate speed
int movingSpeed = 300;

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
    } else if (strcmp(token, "SPEED") == 0) {
        handleSpeed();
    } else {
        Serial.print("ERROR: Unknown command '");
        Serial.print(token);
        Serial.println("'");
    }
}

// AX-12 moving speed register (controls how fast servos move to goal)
#define AX_MOVING_SPEED_L 32

void handleSetPositions() {
    // Peek ahead to count available tokens
    // We need to detect: 6 values (ROS mode) vs 8 values (direct servo mode)
    
    // Save current position in token stream by re-parsing cmdBuffer
    // Count space-separated values after "POS"
    int valueCount = 0;
    char* tempCmd = strdup(cmdBuffer);
    char* saveptr;
    char* token = strtok_r(tempCmd, " ", &saveptr);  // Skip "POS"
    while ((token = strtok_r(NULL, " ", &saveptr)) != NULL) {
        // Stop counting at newline/carriage return
        char* nl = strchr(token, '\r');
        if (nl) *nl = '\0';
        nl = strchr(token, '\n');
        if (nl) *nl = '\0';
        if (strlen(token) > 0) {
            valueCount++;
        }
    }
    free(tempCmd);
    
    // Re-parse original buffer for actual values
    // Reset strtok by calling with original cmd (hacky but works)
    
    if (valueCount == 8) {
        // Direct servo control mode: 8 values, one per servo
        int servoPositions[8];
        int speed = -1;
        
        for (int i = 0; i < 8; i++) {
            char* tok = strtok(NULL, " ");
            if (!tok) {
                Serial.println("ERROR: Expected 8 servo positions");
                return;
            }
            servoPositions[i] = atoi(tok);
            if (servoPositions[i] < 0 || servoPositions[i] > 1023) {
                Serial.print("ERROR: Servo ");
                Serial.print(i+1);
                Serial.println(" position out of range");
                return;
            }
        }
        
        // Optional speed
        char* speedToken = strtok(NULL, " \r\n");
        if (speedToken) {
            speed = atoi(speedToken);
            if (speed >= 0 && speed <= 1023) {
                for (int i = 0; i < NUM_SERVOS; i++) {
                    ax12SetRegister2(SERVO_IDS[i], AX_MOVING_SPEED_L, speed);
                }
            }
        } else {
            for (int i = 0; i < NUM_SERVOS; i++) {
                ax12SetRegister2(SERVO_IDS[i], AX_MOVING_SPEED_L, movingSpeed);
            }
        }
        
        // Send directly to each servo
        for (int i = 0; i < NUM_SERVOS; i++) {
            ax12SetRegister2(SERVO_IDS[i], AX_GOAL_POS_L, servoPositions[i]);
        }
        
        Serial.println("OK");
        
    } else if (valueCount >= 6) {
        // ROS mode: 6 joint values (+ optional speed), map to 8 servos with mirroring
        int rosPositions[6];
        int speed = -1;
        
        for (int i = 0; i < 6; i++) {
            char* tok = strtok(NULL, " ");
            if (!tok) {
                Serial.println("ERROR: Expected 6 joint positions");
                return;
            }
            rosPositions[i] = atoi(tok);
            if (rosPositions[i] < 0 || rosPositions[i] > 1023) {
                Serial.print("ERROR: Joint ");
                Serial.print(i+1);
                Serial.println(" position out of range");
                return;
            }
        }
        
        // Optional speed
        char* speedToken = strtok(NULL, " \r\n");
        if (speedToken) {
            speed = atoi(speedToken);
            if (speed >= 0 && speed <= 1023) {
                for (int i = 0; i < NUM_SERVOS; i++) {
                    ax12SetRegister2(SERVO_IDS[i], AX_MOVING_SPEED_L, speed);
                }
            }
        } else {
            for (int i = 0; i < NUM_SERVOS; i++) {
                ax12SetRegister2(SERVO_IDS[i], AX_MOVING_SPEED_L, movingSpeed);
            }
        }
        
        // Map 6 ROS joints to 8 physical servos with mirroring
        ax12SetRegister2(1, AX_GOAL_POS_L, rosPositions[0]);  // shoulder_yaw
        ax12SetRegister2(2, AX_GOAL_POS_L, rosPositions[1]);  // shoulder_pitch
        ax12SetRegister2(3, AX_GOAL_POS_L, 1023 - rosPositions[1]);  // mirrored
        ax12SetRegister2(4, AX_GOAL_POS_L, rosPositions[2]);  // elbow_pitch
        ax12SetRegister2(5, AX_GOAL_POS_L, 1023 - rosPositions[2]);  // mirrored
        ax12SetRegister2(6, AX_GOAL_POS_L, rosPositions[3]);  // wrist_pitch
        ax12SetRegister2(7, AX_GOAL_POS_L, rosPositions[4]);  // wrist_roll
        ax12SetRegister2(8, AX_GOAL_POS_L, rosPositions[5]);  // gripper
        
        Serial.println("OK");
        
    } else {
        Serial.print("ERROR: Expected 6 (ROS) or 8 (direct) values, got ");
        Serial.println(valueCount);
    }
}

void handleSpeed() {
    char* token = strtok(NULL, " ");
    if (!token) {
        Serial.print("Current speed: ");
        Serial.println(movingSpeed);
        return;
    }
    
    movingSpeed = atoi(token);
    if (movingSpeed < 0 || movingSpeed > 1023) {
        Serial.println("ERROR: Speed out of range (0-1023)");
        movingSpeed = 300;  // Reset to default
        return;
    }
    
    // Apply new speed to all servos
    for (int i = 0; i < NUM_SERVOS; i++) {
        ax12SetRegister2(SERVO_IDS[i], AX_MOVING_SPEED_L, movingSpeed);
    }
    
    Serial.print("SPEED OK: ");
    Serial.println(movingSpeed);
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
