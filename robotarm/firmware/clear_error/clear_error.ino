/*
 * Clear servo errors - reset shutdown flags
 */
#include <ax12.h>

void setup() {
    Serial.begin(115200);
    delay(2000);
    
    Serial.println("Clearing servo errors...");
    ax12Init(1000000);
    delay(500);
    
    // Reset torque on all servos (clears error state)
    for (int id = 1; id <= 10; id++) {
        Serial.print("Resetting servo ");
        Serial.println(id);
        ax12SetRegister(id, 24, 0);  // Torque Enable = 0
        delay(100);
    }
    
    Serial.println("Done. Power cycle the servos now.");
    Serial.println("Disconnect 12V for 10 seconds, then reconnect.");
}

void loop() {
    delay(1000);
}
