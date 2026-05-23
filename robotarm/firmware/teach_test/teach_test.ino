/*
 * PhantomX Reactor - Teach & Recall Test Sketch
 * 
 * Servo ID mapping for PhantomX Reactor:
 *   ID 1: Base
 *   ID 2,3: Shoulder (dual, mirrored)
 *   ID 4,5: Elbow (dual, mirrored)
 *   ID 6: Wrist tilt
 *   ID 7: Wrist rotation
 *   ID 8: Gripper
 */

#include <ax12.h>

// Servo IDs
#define BASE_SERVO      1
#define SHOULDER_L      2
#define SHOULDER_R      3
#define ELBOW_L         4
#define ELBOW_R         5
#define WRIST_TILT      6
#define WRIST_ROT       7
#define GRIPPER         8

#define NUM_SERVOS      8

// AX-12 Register addresses
#define AX_TORQUE_ENABLE    24
#define AX_PRESENT_POS_L    36
#define AX_GOAL_POS_L       30

// Storage for taught positions
int taughtPositions[NUM_SERVOS + 1];  // Index 0 unused, 1-8 for servo IDs
bool hasTaughtPosition = false;

// Movement parameters
int moveSpeed = 5;   // Position units per step (higher = faster)
int moveDelay = 30;  // Milliseconds between steps (higher = slower)

void setup() {
    Serial.begin(115200);
    delay(2000);
    
    Serial.println("################################");
    Serial.println("PhantomX Reactor - Teach & Recall");
    Serial.println("################################");
    Serial.println("");
    
    // Initialize AX-12 at 1Mbps
    ax12Init(1000000);
    
    Serial.println("AX-12 Initialized!");
    Serial.println("");
    
    // Auto-teach: Save current positions on startup
    Serial.println("Auto-teaching current positions...");
    teachCurrentPosition();
    
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
            case 'e':
                checkAllErrors();
                break;
            case 't':
                teachCurrentPosition();
                break;
            case 'r':
                recallPosition();
                break;
            case 's':
                setSpeed();
                break;
            case 'd':
                setDelay();
                break;
            case 'v':
                showSettings();
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
    Serial.println("  3 - Gripper close (position ~50)");
    Serial.println("  4 - Gripper open (position ~256)");
    Serial.println("  e - Read all servo error flags");
    Serial.println("  t - Teach (save current positions)");
    Serial.println("  r - Recall (move to saved positions)");
    Serial.println("  s - Set movement speed (step size)");
    Serial.println("  d - Set movement delay (ms between steps)");
    Serial.println("  v - Show current speed/delay settings");
    Serial.println("  h/? - Show this menu");
    Serial.println("");
    if (hasTaughtPosition) {
        Serial.print("Status: Taught position saved");
    } else {
        Serial.println("Status: NO taught position saved!");
    }
    Serial.println("");
}

void relaxServos() {
    Serial.println("Relaxing all servos...");
    for (int id = 1; id <= NUM_SERVOS; id++) {
        ax12SetRegister(id, AX_TORQUE_ENABLE, 0);
        delay(50);
    }
    Serial.println("Done. All servos relaxed.");
    Serial.println("");
}

void holdServos() {
    Serial.println("Holding all servos...");
    for (int id = 1; id <= NUM_SERVOS; id++) {
        ax12SetRegister(id, AX_TORQUE_ENABLE, 1);
        delay(50);
    }
    Serial.println("Done. All servos holding.");
    Serial.println("");
}

void printPositions() {
    Serial.println("Joint Positions:");
    
    const char* names[] = {"", "Base", "Shoulder L", "Shoulder R", "Elbow L", "Elbow R", "Wrist Tilt", "Wrist Rot", "Gripper"};
    
    for (int id = 1; id <= NUM_SERVOS; id++) {
        int pos = ax12GetRegister(id, AX_PRESENT_POS_L, 2);
        Serial.print("  ");
        Serial.print(names[id]);
        Serial.print(" (");
        Serial.print(id);
        Serial.print("): ");
        if (pos == -1) {
            Serial.println("NO RESPONSE");
        } else {
            Serial.println(pos);
        }
    }
    Serial.println("");
}

void gripperClose() {
    Serial.println("Closing gripper...");
    moveToPosition(GRIPPER, 50);
    Serial.println("Done.");
    Serial.println("");
}

void gripperOpen() {
    Serial.println("Opening gripper...");
    moveToPosition(GRIPPER, 256);
    Serial.println("Done.");
    Serial.println("");
}

void teachCurrentPosition() {
    Serial.println("Teaching current position...");
    
    bool success = true;
    
    for (int id = 1; id <= NUM_SERVOS; id++) {
        int pos = ax12GetRegister(id, AX_PRESENT_POS_L, 2);
        
        if (pos == -1) {
            Serial.print("WARNING: Servo ");
            Serial.print(id);
            Serial.println(" not responding, skipping...");
            success = false;
            continue;
        }
        
        taughtPositions[id] = pos;
        Serial.print("  Servo ");
        Serial.print(id);
        Serial.print(": ");
        Serial.println(pos);
    }
    
    if (success) {
        hasTaughtPosition = true;
        Serial.println("Position taught successfully!");
    } else {
        Serial.println("Partial teach completed (some servos missing).");
    }
    Serial.println("");
}

void recallPosition() {
    if (!hasTaughtPosition) {
        Serial.println("ERROR: No taught position available!");
        Serial.println("Use 't' command first to teach a position.");
        Serial.println("");
        return;
    }
    
    Serial.println("Recalling taught position...");
    Serial.print("Target: [");
    for (int i = 1; i <= NUM_SERVOS; i++) {
        Serial.print(taughtPositions[i]);
        if (i < NUM_SERVOS) Serial.print(", ");
    }
    Serial.println("]");
    Serial.println("");
    
    // Enable torque on all servos
    holdServos();
    delay(500);
    
    // Move all servos smoothly to target positions
    moveToPositionsSmooth(taughtPositions);
    
    Serial.println("Recall complete!");
    Serial.println("");
}

void setSpeed() {
    Serial.print("Current step size: ");
    Serial.println(moveSpeed);
    Serial.print("Enter new step size (1-50): ");
    
    while (!Serial.available()) {
        delay(10);
    }
    
    int newSpeed = Serial.parseInt();
    
    if (newSpeed >= 1 && newSpeed <= 50) {
        moveSpeed = newSpeed;
        Serial.print("Step size set to ");
        Serial.println(moveSpeed);
    } else {
        Serial.println("Invalid. Must be between 1 and 50.");
        Serial.println("Lower = slower/smooth, Higher = faster");
    }
    Serial.println("");
}

void setDelay() {
    Serial.print("Current delay: ");
    Serial.println(moveDelay);
    Serial.print("Enter new delay in ms (10-200): ");
    
    while (!Serial.available()) {
        delay(10);
    }
    
    int newDelay = Serial.parseInt();
    
    if (newDelay >= 10 && newDelay <= 200) {
        moveDelay = newDelay;
        Serial.print("Delay set to ");
        Serial.print(moveDelay);
        Serial.println("ms");
    } else {
        Serial.println("Invalid. Must be between 10 and 200ms.");
        Serial.println("Higher = slower");
    }
    Serial.println("");
}

void showSettings() {
    Serial.println("=== Movement Settings ===");
    Serial.print("Step size: ");
    Serial.println(moveSpeed);
    Serial.print("Delay between steps: ");
    Serial.print(moveDelay);
    Serial.println("ms");
    Serial.println("");
    Serial.println("Tips:");
    Serial.println("  - For slow smooth motion: step=3, delay=50");
    Serial.println("  - For medium speed: step=10, delay=30");
    Serial.println("  - For fast motion: step=30, delay=20");
    Serial.println("");
}

// Move single servo to position (blocking)
void moveToPosition(int servoId, int targetPos) {
    int currentPos = ax12GetRegister(servoId, AX_PRESENT_POS_L, 2);
    
    if (currentPos == -1) {
        Serial.print("ERROR: Cannot read servo ");
        Serial.println(servoId);
        return;
    }
    
    // Simple direct move (can be enhanced with interpolation)
    ax12SetRegister2(servoId, AX_GOAL_POS_L, targetPos);
    
    // Wait until reached
    while (true) {
        int moving = ax12GetRegister(servoId, 46, 1);  // Moving flag
        if (moving == 0 || moving == -1) break;
        delay(10);
    }
}

// Move all servos smoothly using interpolation
void moveToPositionsSmooth(int* targets) {
    int currentPositions[NUM_SERVOS + 1];
    bool done[NUM_SERVOS + 1];
    
    // Read current positions
    for (int id = 1; id <= NUM_SERVOS; id++) {
        currentPositions[id] = ax12GetRegister(id, AX_PRESENT_POS_L, 2);
        done[id] = false;
        
        if (currentPositions[id] == -1) {
            Serial.print("WARNING: Servo ");
            Serial.print(id);
            Serial.println(" not responding, excluding from move");
            done[id] = true;  // Skip this servo
        }
    }
    
    // Interpolation loop
    bool anyMoving = true;
    while (anyMoving) {
        anyMoving = false;
        
        for (int id = 1; id <= NUM_SERVOS; id++) {
            if (done[id]) continue;
            
            int error = targets[id] - currentPositions[id];
            
            // Check if close enough to target
            if (abs(error) <= moveSpeed) {
                // Final move to exact position
                ax12SetRegister2(id, AX_GOAL_POS_L, targets[id]);
                done[id] = true;
                currentPositions[id] = targets[id];
            } else {
                // Step toward target
                int step = (error > 0) ? moveSpeed : -moveSpeed;
                currentPositions[id] += step;
                ax12SetRegister2(id, AX_GOAL_POS_L, currentPositions[id]);
                anyMoving = true;
            }
        }
        
        // Small delay between steps
        delay(moveDelay);
    }
    
    // Wait for all servos to finish
    delay(500);
}

void checkAllErrors() {
    Serial.println("=== Servo Error Status ===");
    Serial.println("");
    
    const char* names[] = {"", "Base", "Shoulder L", "Shoulder R", "Elbow L", "Elbow R", "Wrist Tilt", "Wrist Rot", "Gripper"};
    
    for (int id = 1; id <= NUM_SERVOS; id++) {
        Serial.print(names[id]);
        Serial.print(" (ID=");
        Serial.print(id);
        Serial.print("): ");
        
        int moving = ax12GetRegister(id, 46, 1);
        int load = ax12GetRegister(id, 40, 2);
        int voltage = ax12GetRegister(id, 42, 1);
        int temp = ax12GetRegister(id, 43, 1);
        
        if (moving == -1) {
            Serial.println("NO RESPONSE");
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
    Serial.println("To clear: send 0 (relax), then power cycle.");
    Serial.println("");
}
