# ArbotiX-M Troubleshooting Guide

## Upload Succeeded But No Serial Output

If `arduino-cli upload` completes successfully but you get no serial output:

### Possible Causes & Solutions

#### 1. **Board Needs Manual Reset**
The ArbotiX-M may require pressing the reset button just before upload.

**Solution:**
```bash
# Press reset button on ArbotiX-M, then immediately run:
arduino-cli upload -p /dev/ttyUSB0 -b arbotix:avr:arbotix ./basic_test
```

#### 2. **Bootloader Issue**
The bootloader may not be running or is corrupted.

**Check bootloader LED:** When you power on the board, does an LED blink briefly?

**Solution:** You may need to burn the bootloader using an ISP programmer:
```bash
arduino-cli burn-bootloader -b arbotix:avr:arbotix -p /dev/ttyUSB0 --programmer avrispmkii
```

#### 3. **Clock Speed Mismatch**
The board might be running at a different clock speed than expected (16MHz).

**Check:** Verify crystal oscillator is present and intact on the board.

#### 4. **FTDI Connection Issue**
- Double-check FTDI cable orientation
- Ensure all 6 pins are making contact
- Try a different FTDI cable

#### 5. **Baud Rate Mismatch**
Try different baud rates in your sketch:
```cpp
Serial.begin(38400);   // ArbotiX default
// or
Serial.begin(9600);    // Common fallback
```

#### 6. **Power Issues**
- With VSEL=USB, only the microcontroller gets power (~5V from USB)
- This should be enough for basic serial communication
- If servos are connected but unpowered, they shouldn't affect serial

---

## Test Without Servos Connected

For initial testing, disconnect all servo cables from the ArbotiX-M. This eliminates potential issues with:
- Unpowered servos drawing current
- Incorrect servo IDs causing bus conflicts
- Short circuits in servo wiring

---

## Minimal Test Sketch

Use this minimal sketch to verify basic functionality:

```cpp
void setup() {
    Serial.begin(38400);
    while (!Serial) {
        ; // Wait for serial port to connect
    }
    Serial.println("TEST OK");
}

void loop() {
    Serial.print("Uptime: ");
    Serial.println(millis());
    delay(1000);
}
```

Upload and test with:
```bash
python3 -c "
import serial, time
ser = serial.Serial('/dev/ttyUSB0', 38400, timeout=2)
time.sleep(2)
for i in range(5):
    if ser.in_waiting:
        print(ser.read(ser.in_waiting).decode())
    time.sleep(0.5)
"
```

---

## Hardware Checklist

- [ ] FTDI cable firmly seated (all 6 pins)
- [ ] FTDI cable orientation correct (black=GND aligned)
- [ ] VSEL jumper set appropriately (USB for programming)
- [ ] USB cable is data-capable (not charge-only)
- [ ] Board shows signs of life (LEDs, warmth)
- [ ] No short circuits on board
- [ ] Crystal oscillator intact (16MHz)

---

## Next Steps

If basic serial still doesn't work:

1. **Try Arduino IDE** - Sometimes the official IDE handles timing better
2. **Check with multimeter** - Verify 5V at FTDI header when VSEL=USB
3. **Try different computer/USB port** - Rule out host issues
4. **Inspect board** - Look for damaged components, cold solder joints

---

## Success Indicators

When working correctly, you should see:
- ✓ Upload completes without errors
- ✓ Serial output appears within 2 seconds of reset
- ✓ Commands sent via serial receive responses
- ✓ Onboard LED (if present) may blink during operation
