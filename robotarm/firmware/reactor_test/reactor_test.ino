/*
 * PhantomX Reactor - Basic Test Sketch
 * 
 * This sketch tests communication with the AX-12A Dynamixel servos
 * and provides basic control via serial commands.
 */

#include <ax12.h>
#include <BioloidController.h>

// Servo IDs for PhantomX Reactor
#define BASE_SERVO      1
#define SHOULDER_SERVO  2
#define ELBOW_SERVO     3
#define WRIST_SERVO     4
#define GRIPPER_SERVO   5

// AX-12 Register addresses
#define AX_TORQUE_ENABLE    24
#define AX_PRESENT_POS_L    36
#define AX_GOAL_POS_L       30

void setup() {
    // Initialize serial communication
    Serial.begin(115200);
    
    // Wait for serial port to connect
    delay(1000);
    
    Serial.println("################################");
    Serial.println("PhantomX Reactor - CLI Test");
    Serial.println("################################");
    
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
                checkGripperLimits();
                break;
            case '7':
                gripperStep(25);   // Open slightly
                break;
            case '8':
                gripperStep(-25);  // Close slightly
                break;
            case '9':
                gripperStep(50);   // Open more
                break;
            case 'c':
            case 'C':
                gripperStep(-50);  // Close more
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
    Serial.println("  0 - Relax servos (power off)");
    Serial.println("  1 - Hold servos (power on)");
    Serial.println("  2 - Get joint positions");
    Serial.println("  3 - Gripper close (preset)");
    Serial.println("  4 - Gripper open (preset)");
    Serial.println("  5 - Test movement sequence");
    Serial.println("  6 - Check servo angle limits");
    Serial.println("  7 - Gripper +25 (slightly open)");
    Serial.println("  8 - Gripper -25 (slightly close)");
    Serial.println("  9 - Gripper +50 (more open)");
    Serial.println("  c - Gripper -50 (more close)");
    Serial.println("  h/? - Show this menu");
    Serial.println("");
}

void relaxServos() {
    Serial.println("Relaxing all servos...");
    ax12SetRegister(BASE_SERVO, AX_TORQUE_ENABLE, 0);
    ax12SetRegister(SHOULDER_SERVO, AX_TORQUE_ENABLE, 0);
    ax12SetRegister(ELBOW_SERVO, AX_TORQUE_ENABLE, 0);
    ax12SetRegister(WRIST_SERVO, AX_TORQUE_ENABLE, 0);
    ax12SetRegister(GRIPPER_SERVO, AX_TORQUE_ENABLE, 0);
    Serial.println("Done.");
}

void holdServos() {
    Serial.println("Holding all servos...");
    ax12SetRegister(BASE_SERVO, AX_TORQUE_ENABLE, 1);
    ax12SetRegister(SHOULDER_SERVO, AX_TORQUE_ENABLE, 1);
    ax12SetRegister(ELBOW_SERVO, AX_TORQUE_ENABLE, 1);
    ax12SetRegister(WRIST_SERVO, AX_TORQUE_ENABLE, 1);
    ax12SetRegister(GRIPPER_SERVO, AX_TORQUE_ENABLE, 1);
    Serial.println("Done.");
}

void printPositions() {
    Serial.println("Joint Positions:");
    
    int pos = ax12GetRegister(BASE_SERVO, AX_PRESENT_POS_L, 2);
    Serial.print("  Base:    ");
    Serial.println(pos);
    
    pos = ax12GetRegister(SHOULDER_SERVO, AX_PRESENT_POS_L, 2);
    Serial.print("  Shoulder: ");
    Serial.println(pos);
    
    pos = ax12GetRegister(ELBOW_SERVO, AX_PRESENT_POS_L, 2);
    Serial.print("  Elbow:    ");
    Serial.println(pos);
    
    pos = ax12GetRegister(WRIST_SERVO, AX_PRESENT_POS_L, 2);
    Serial.print("  Wrist:    ");
    Serial.println(pos);
    
    pos = ax12GetRegister(GRIPPER_SERVO, AX_PRESENT_POS_L, 2);
    Serial.print("  Gripper:  ");
    Serial.println(pos);
}

void gripperClose() {
    Serial.println("Closing gripper...");
    // Gripper positions based on observed range (~612 current)
    // Adjust these values based on your specific gripper mechanics
    // Try: 500 = closed, 700 = open (modify if needed)
    int closePos = 500;
    ax12SetRegister2(GRIPPER_SERVO, AX_GOAL_POS_L, closePos);
    Serial.print("Moving to position: ");
    Serial.println(closePos);
    delay(1500);  // Wait longer for gripper to complete movement
    Serial.println("Done.");
}

void gripperOpen() {
    Serial.println("Opening gripper...");
    int openPos = 700;
    ax12SetRegister2(GRIPPER_SERVO, AX_GOAL_POS_L, openPos);
    Serial.print("Moving to position: ");
    Serial.println(openPos);
    delay(1500);  // Wait longer for gripper to complete movement
    Serial.println("Done.");
}

void testMovement() {
    Serial.println("Running test movement sequence...");
    Serial.println("(Each movement takes 2-3 seconds)");
    
    // Wake up all servos
    holdServos();
    delay(1000);
    
    // Move base left-right (slowly)
    Serial.println("\n1. Moving base left...");
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 400);
    delay(3000);  // 3 seconds for slow, visible movement
    
    Serial.println("2. Moving base right...");
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 624);
    delay(3000);
    
    Serial.println("3. Centering base...");
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 512);  // Center
    delay(2000);
    
    // Move shoulder up-down
    Serial.println("\n4. Moving shoulder up...");
    ax12SetRegister2(SHOULDER_SERVO, AX_GOAL_POS_L, 300);
    delay(3000);
    
    Serial.println("5. Moving shoulder down...");
    ax12SetRegister2(SHOULDER_SERVO, AX_GOAL_POS_L, 512);
    delay(3000);
    
    // Move elbow
    Serial.println("\n6. Moving elbow up...");
    ax12SetRegister2(ELBOW_SERVO, AX_GOAL_POS_L, 500);
    delay(3000);
    
    Serial.println("7. Moving elbow down...");
    ax12SetRegister2(ELBOW_SERVO, AX_GOAL_POS_L, 700);
    delay(3000);
    
    // Return to observed home positions
    Serial.println("\n8. Returning to home position...");
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 512);
    ax12SetRegister2(SHOULDER_SERVO, AX_GOAL_POS_L, 359);
    ax12SetRegister2(ELBOW_SERVO, AX_GOAL_POS_L, 660);
    ax12SetRegister2(WRIST_SERVO, AX_GOAL_POS_L, 410);
    delay(3000);
    
    Serial.println("\n✓ Test sequence complete.");
    Serial.println("");
}

void checkGripperLimits() {
    Serial.println("=== Gripper Servo Configuration ===");
    
    int cwLimit = ax12GetRegister(GRIPPER_SERVO, 6, 2);   // CW Angle Limit (min)
    int ccwLimit = ax12GetRegister(GRIPPER_SERVO, 8, 2);  // CCW Angle Limit (max)
    int maxTorque = ax12GetRegister(GRIPPER_SERVO, 14, 2); // Max Torque
    int currentPos = ax12GetRegister(GRIPPER_SERVO, AX_PRESENT_POS_L, 2);
    
    Serial.print("Current Position: ");
    Serial.println(currentPos);
    Serial.print("CW Limit (min): ");
    Serial.println(cwLimit);
    Serial.print("CCW Limit (max): ");
    Serial.println(ccwLimit);
    Serial.print("Max Torque: ");
    Serial.println(maxTorque);
    
    if (cwLimit == 0 && ccwLimit == 1023) {
        Serial.println("");
        Serial.println("WARNING: No angle limits configured!");
        Serial.println("Servo can move full 0-1023 range.");
        Serial.println("Use incremental commands (7,8,9,c) carefully.");
        Serial.println("Listen for grinding or binding sounds.");
    } else {
        Serial.println("");
        Serial.print("Safe range: ");
        Serial.print(cwLimit);
        Serial.print(" to ");
        Serial.println(ccwLimit);
    }
    Serial.println("");
}

void gripperStep(int delta) {
    // Get current position
    int currentPos = ax12GetRegister(GRIPPER_SERVO, AX_PRESENT_POS_L, 2);
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
    
    ax12SetRegister2(GRIPPER_SERVO, AX_GOAL_POS_L, newPos);
    
    // Wait and verify
    delay(1000);
    int actualPos = ax12GetRegister(GRIPPER_SERVO, AX_PRESENT_POS_L, 2);
    Serial.print("Actual position: ");
    Serial.println(actualPos);
    
    if (abs(actualPos - newPos) > 10) {
        Serial.println("WARNING: Servo may have hit mechanical limit!");
    }
    Serial.println("");
}
