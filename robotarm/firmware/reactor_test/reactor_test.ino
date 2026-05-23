/*
 * PhantomX Reactor - Basic Test Sketch
 * 
 * Correct servo ID mapping for PhantomX Reactor Arm:
 *   ID 1: Base
 *   ID 2,3: Shoulder (dual, mirrored)
 *   ID 4,5: Elbow (dual, mirrored)
 *   ID 6: Wrist tilt
 *   ID 7: Wrist rotation
 *   ID 8: Gripper
 */

#include <ax12.h>
#include <BioloidController.h>

// Servo IDs for PhantomX Reactor
#define BASE_SERVO      1
#define SHOULDER_L      2  // Left shoulder
#define SHOULDER_R      3  // Right shoulder (mirrored)
#define ELBOW_L         4  // Left elbow
#define ELBOW_R         5  // Right elbow (mirrored)
#define WRIST_TILT      6
#define WRIST_ROT       7
#define GRIPPER         8

// AX-12 Register addresses
#define AX_TORQUE_ENABLE    24
#define AX_PRESENT_POS_L    36
#define AX_GOAL_POS_L       30

void setup() {
    // Initialize serial communication at 115200 baud
    Serial.begin(115200);
    
    // Wait for serial port to connect
    delay(2000);
    
    Serial.println("################################");
    Serial.println("PhantomX Reactor - CLI Test");
    Serial.println("################################");
    Serial.println("");
    Serial.println("Servo Configuration:");
    Serial.println("  ID 1: Base");
    Serial.println("  ID 2,3: Shoulder (dual)");
    Serial.println("  ID 4,5: Elbow (dual)");
    Serial.println("  ID 6: Wrist tilt");
    Serial.println("  ID 7: Wrist rotation");
    Serial.println("  ID 8: Gripper");
    Serial.println("");
    
    // Initialize AX-12 communication at 1Mbps
    ax12Init(1000000);
    
    Serial.println("AX-12 Initialized!");
    Serial.println("");
    printMenu();
}

void loop() {
    if (Serial.available()) {
        char cmd = Serial.read();
        
        switch(cmd) {
            case '0':
                relaxServos();
                break;
            case '1':
                holdServos();
                break;
            case '2':
                printPositions();
                break;
            case '3':
                gripperClose();
                break;
            case '4':
                gripperOpen();
                break;
            case '5':
                testMovement();
                break;
            case '6':
                checkServoLimits();
                break;
            case '7':
                gripperStep(10);   // Slightly open (small steps for fine control)
                break;
            case '8':
                gripperStep(-10);  // Slightly close
                break;
            case '9':
                gripperStep(25);   // More open
                break;
            case 'c':
            case 'C':
                gripperStep(-25);  // More close
                break;
            case 'e':
                checkAllErrors();
                break;
            case 'h':
            case '?':
                printMenu();
                break;
            default:
                Serial.println("Unknown command. Press 'h' for help.");
                break;
        }
    }
}

void printMenu() {
    Serial.println("Commands:");
    Serial.println("  0 - Relax all servos (torque off)");
    Serial.println("  1 - Hold all servos (torque on)");
    Serial.println("  2 - Get joint positions");
    Serial.println("  3 - Gripper close (pos ~50)");
    Serial.println("  4 - Gripper open (pos ~256)");
    Serial.println("  5 - Test movement sequence");
    Serial.println("  6 - Check servo angle limits");
    Serial.println("  7 - Gripper +10 (fine open)");
    Serial.println("  8 - Gripper -10 (fine close)");
    Serial.println("  9 - Gripper +25 (coarse open)");
    Serial.println("  c - Gripper -25 (coarse close)");
    Serial.println("  e - Read all servo error flags");
    Serial.println("  h/? - Show this menu");
    Serial.println("");
    Serial.println("NOTE: Gripper range is 0-512 (rotating disc)");
    Serial.println("  0 = closed, 256 = open, 512 = closed");
    Serial.println("");
}

void relaxServos() {
    Serial.println("Relaxing all servos...");
    for (int id = 1; id <= 8; id++) {
        ax12SetRegister(id, AX_TORQUE_ENABLE, 0);
        delay(50);
    }
    Serial.println("Done. All servos relaxed (free movement).");
}

void holdServos() {
    Serial.println("Holding all servos...");
    for (int id = 1; id <= 8; id++) {
        ax12SetRegister(id, AX_TORQUE_ENABLE, 1);
        delay(50);
    }
    Serial.println("Done. All servos holding position.");
}

void printPositions() {
    Serial.println("Joint Positions:");
    
    int pos = ax12GetRegister(BASE_SERVO, AX_PRESENT_POS_L, 2);
    Serial.print("  Base:           ");
    if (pos == -1) Serial.println("NO RESPONSE"); else Serial.println(pos);
    
    pos = ax12GetRegister(SHOULDER_L, AX_PRESENT_POS_L, 2);
    Serial.print("  Shoulder L (2): ");
    if (pos == -1) Serial.println("NO RESPONSE"); else Serial.println(pos);
    
    pos = ax12GetRegister(SHOULDER_R, AX_PRESENT_POS_L, 2);
    Serial.print("  Shoulder R (3): ");
    if (pos == -1) Serial.println("NO RESPONSE"); else Serial.println(pos);
    
    pos = ax12GetRegister(ELBOW_L, AX_PRESENT_POS_L, 2);
    Serial.print("  Elbow L (4):    ");
    if (pos == -1) Serial.println("NO RESPONSE"); else Serial.println(pos);
    
    pos = ax12GetRegister(ELBOW_R, AX_PRESENT_POS_L, 2);
    Serial.print("  Elbow R (5):    ");
    if (pos == -1) Serial.println("NO RESPONSE"); else Serial.println(pos);
    
    pos = ax12GetRegister(WRIST_TILT, AX_PRESENT_POS_L, 2);
    Serial.print("  Wrist Tilt (6): ");
    if (pos == -1) Serial.println("NO RESPONSE"); else Serial.println(pos);
    
    pos = ax12GetRegister(WRIST_ROT, AX_PRESENT_POS_L, 2);
    Serial.print("  Wrist Rot (7):  ");
    if (pos == -1) Serial.println("NO RESPONSE"); else Serial.println(pos);
    
    pos = ax12GetRegister(GRIPPER, AX_PRESENT_POS_L, 2);
    Serial.print("  Gripper (8):    ");
    if (pos == -1) Serial.println("NO RESPONSE"); else Serial.println(pos);
    
    Serial.println("");
}

void gripperClose() {
    Serial.println("Closing gripper...");
    // Gripper range: 0=closed, ~256=open, 512=closed again (rotating disc)
    int closePos = 50;  // Near fully closed
    ax12SetRegister2(GRIPPER, AX_GOAL_POS_L, closePos);
    Serial.print("Moving to position: ");
    Serial.println(closePos);
    delay(1500);
    Serial.println("Done.");
}

void gripperOpen() {
    Serial.println("Opening gripper...");
    // Gripper range: 0=closed, ~256=open, 512=closed again (rotating disc)
    int openPos = 256;  // Midpoint = fully open
    ax12SetRegister2(GRIPPER, AX_GOAL_POS_L, openPos);
    Serial.print("Moving to position: ");
    Serial.println(openPos);
    delay(1500);
    Serial.println("Done.");
}

void gripperStep(int delta) {
    int currentPos = ax12GetRegister(GRIPPER, AX_PRESENT_POS_L, 2);
    
    if (currentPos == -1) {
        Serial.println("ERROR: Cannot read gripper position!");
        Serial.println("");
        return;
    }
    
    int newPos = currentPos + delta;
    
    // Clamp to valid range
    if (newPos < 0) newPos = 0;
    if (newPos > 1023) newPos = 1023;
    
    Serial.print("Gripper: ");
    Serial.print(currentPos);
    Serial.print(" -> ");
    Serial.print(newPos);
    Serial.print(" (delta: ");
    Serial.print(delta);
    Serial.println(")");
    
    ax12SetRegister2(GRIPPER, AX_GOAL_POS_L, newPos);
    
    // Wait and verify
    delay(1000);
    int actualPos = ax12GetRegister(GRIPPER, AX_PRESENT_POS_L, 2);
    Serial.print("Actual position: ");
    Serial.println(actualPos);
    
    if (abs(actualPos - newPos) > 10) {
        Serial.println("WARNING: Servo may have hit mechanical limit or is in error state!");
    }
    Serial.println("");
}

void testMovement() {
    Serial.println("Running test movement sequence...");
    Serial.println("(Each movement takes 2-3 seconds)");
    
    // Wake up all servos
    holdServos();
    delay(1000);
    
    // Move base left-right
    Serial.println("\n1. Moving base left...");
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 400);
    delay(3000);
    
    Serial.println("2. Moving base right...");
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 624);
    delay(3000);
    
    Serial.println("3. Centering base...");
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 512);
    delay(2000);
    
    // Move shoulder (both servos)
    Serial.println("\n4. Moving shoulder up...");
    ax12SetRegister2(SHOULDER_L, AX_GOAL_POS_L, 400);
    ax12SetRegister2(SHOULDER_R, AX_GOAL_POS_L, 624);  // Mirrored
    delay(3000);
    
    Serial.println("5. Moving shoulder down...");
    ax12SetRegister2(SHOULDER_L, AX_GOAL_POS_L, 512);
    ax12SetRegister2(SHOULDER_R, AX_GOAL_POS_L, 512);
    delay(3000);
    
    // Move elbow (both servos)
    Serial.println("\n6. Moving elbow up...");
    ax12SetRegister2(ELBOW_L, AX_GOAL_POS_L, 400);
    ax12SetRegister2(ELBOW_R, AX_GOAL_POS_L, 624);  // Mirrored
    delay(3000);
    
    Serial.println("7. Moving elbow down...");
    ax12SetRegister2(ELBOW_L, AX_GOAL_POS_L, 512);
    ax12SetRegister2(ELBOW_R, AX_GOAL_POS_L, 512);
    delay(3000);
    
    // Return to home positions
    Serial.println("\n8. Returning to home position...");
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 512);
    ax12SetRegister2(SHOULDER_L, AX_GOAL_POS_L, 512);
    ax12SetRegister2(SHOULDER_R, AX_GOAL_POS_L, 512);
    ax12SetRegister2(ELBOW_L, AX_GOAL_POS_L, 512);
    ax12SetRegister2(ELBOW_R, AX_GOAL_POS_L, 512);
    ax12SetRegister2(WRIST_TILT, AX_GOAL_POS_L, 512);
    ax12SetRegister2(WRIST_ROT, AX_GOAL_POS_L, 512);
    ax12SetRegister2(GRIPPER, AX_GOAL_POS_L, 600);
    delay(3000);
    
    Serial.println("\n✓ Test sequence complete.");
    Serial.println("");
}

void checkServoLimits() {
    Serial.println("=== Servo Angle Limits ===");
    Serial.println("");
    
    const char* names[] = {"Base", "Shoulder L", "Shoulder R", "Elbow L", "Elbow R", "Wrist Tilt", "Wrist Rot", "Gripper"};
    byte ids[] = {1, 2, 3, 4, 5, 6, 7, 8};
    
    for (int i = 0; i < 8; i++) {
        Serial.print(names[i]);
        Serial.print(" (ID=");
        Serial.print(ids[i]);
        Serial.print("): ");
        
        int cwLimit = ax12GetRegister(ids[i], 6, 2);
        int ccwLimit = ax12GetRegister(ids[i], 8, 2);
        
        if (cwLimit == -1 || ccwLimit == -1) {
            Serial.println("NO RESPONSE");
            continue;
        }
        
        Serial.print("CW=");
        Serial.print(cwLimit);
        Serial.print(", CCW=");
        Serial.println(ccwLimit);
    }
    
    Serial.println("");
}

void checkAllErrors() {
    Serial.println("=== Servo Error Status ===");
    Serial.println("");
    
    const char* names[] = {"Base", "Shoulder L", "Shoulder R", "Elbow L", "Elbow R", "Wrist Tilt", "Wrist Rot", "Gripper"};
    byte ids[] = {1, 2, 3, 4, 5, 6, 7, 8};
    
    for (int i = 0; i < 8; i++) {
        Serial.print(names[i]);
        Serial.print(" (ID=");
        Serial.print(ids[i]);
        Serial.print("): ");
        
        int moving = ax12GetRegister(ids[i], 46, 1);
        int load = ax12GetRegister(ids[i], 40, 2);
        int voltage = ax12GetRegister(ids[i], 42, 1);
        int temp = ax12GetRegister(ids[i], 43, 1);
        
        if (moving == -1) {
            Serial.println("NO RESPONSE - check connection/power");
            continue;
        }
        
        Serial.print("Moving=");
        Serial.print(moving);
        Serial.print(", Load=");
        Serial.print(load);
        Serial.print(", Voltage=");
        Serial.print(voltage / 10.0);
        Serial.print("V, Temp=");
        Serial.print(temp);
        Serial.println("C");
    }
    
    Serial.println("");
    Serial.println("If LED is blinking, that servo is in SHUTDOWN state.");
    Serial.println("Common causes:");
    Serial.println("  - Overload (mechanical binding/stall)");
    Serial.println("  - Overheating (>70C)");
    Serial.println("  - Input voltage outside 6-14V");
    Serial.println("");
    Serial.println("To clear: send 0 (relax), then power cycle the servo.");
    Serial.println("");
}
