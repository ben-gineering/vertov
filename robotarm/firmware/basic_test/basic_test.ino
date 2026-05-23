/*
 * Basic Test - No servo initialization
 * Just tests serial communication and LED
 */

void setup() {
    // Initialize serial at 38400 baud (ArbotiX default)
    Serial.begin(38400);
    
    // Wait for serial to connect
    delay(2000);
    
    Serial.println("################################");
    Serial.println("ArbotiX-M Basic Test");
    Serial.println("################################");
    Serial.println("");
    Serial.println("Board is alive and responding!");
    Serial.println("");
    Serial.println("Commands:");
    Serial.println("  h - Show this menu");
    Serial.println("  l - Toggle LED (if present)");
    Serial.println("  t - Print timestamp");
    Serial.println("");
}

unsigned long counter = 0;

void loop() {
    // Blink indicator (using counter, may not have physical LED)
    counter++;
    
    if (Serial.available()) {
        char cmd = Serial.read();
        
        switch(cmd) {
            case 'h':
                Serial.println("");
                Serial.println("=== Help Menu ===");
                Serial.println("  h - Show this menu");
                Serial.println("  l - Toggle LED");
                Serial.println("  t - Print uptime");
                Serial.println("");
                break;
                
            case 'l':
                Serial.println("LED toggle command received");
                // Note: ArbotiX-M may not have user LED
                break;
                
            case 't':
                Serial.print("Uptime: ");
                Serial.print(millis());
                Serial.println(" ms");
                break;
                
            default:
                Serial.print("Unknown command: ");
                Serial.println(cmd);
                Serial.println("Send 'h' for help");
                break;
        }
    }
    
    // Small delay
    delay(100);
}
