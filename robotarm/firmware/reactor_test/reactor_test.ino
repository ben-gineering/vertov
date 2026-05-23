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
    Serial.println("  3 - Gripper close");
    Serial.println("  4 - Gripper open");
    Serial.println("  5 - Test movement sequence");
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
    ax12SetRegister2(GRIPPER_SERVO, AX_GOAL_POS_L, 150);  // Adjust value as needed
    delay(500);
    Serial.println("Done.");
}

void gripperOpen() {
    Serial.println("Opening gripper...");
    ax12SetRegister2(GRIPPER_SERVO, AX_GOAL_POS_L, 350);  // Adjust value as needed
    delay(500);
    Serial.println("Done.");
}

void testMovement() {
    Serial.println("Running test movement sequence...");
    
    // Wake up all servos
    holdServos();
    delay(500);
    
    // Move base left-right
    Serial.println("Moving base...");
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 300);
    delay(1000);
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 700);
    delay(1000);
    ax12SetRegister2(BASE_SERVO, AX_GOAL_POS_L, 512);  // Center
    delay(500);
    
    // Move shoulder up-down
    Serial.println("Moving shoulder...");
    ax12SetRegister2(SHOULDER_SERVO, AX_GOAL_POS_L, 400);
    delay(1000);
    ax12SetRegister2(SHOULDER_SERVO, AX_GOAL_POS_L, 600);
    delay(1000);
    ax12SetRegister2(SHOULDER_SERVO, AX_GOAL_POS_L, 512);  // Center
    delay(500);
    
    // Move elbow
    Serial.println("Moving elbow...");
    ax12SetRegister2(ELBOW_SERVO, AX_GOAL_POS_L, 400);
    delay(1000);
    ax12SetRegister2(ELBOW_SERVO, AX_GOAL_POS_L, 600);
    delay(1000);
    ax12SetRegister2(ELBOW_SERVO, AX_GOAL_POS_L, 512);  // Center
    delay(500);
    
    Serial.println("Test sequence complete.");
    Serial.println("");
}
