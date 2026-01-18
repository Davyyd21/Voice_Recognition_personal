import paho.mqtt.client as mqtt
from gpiozero import LED, Motor
import busio
import board
from machine_i2c_lcd import I2cLcd
from time import sleep
led = LED(22)
motor = Motor(forward=27, backward=17)

I2C_ADDR = 0x27
I2C_NUM_ROWS = 2
I2C_NUM_COLS = 16

# Initialize I2C and LCD objects
i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)

# for ESP8266, uncomment the following line
#i2c = SoftI2C(sda=Pin(4), scl=Pin(5), freq=400000)

lcd = I2cLcd(i2c, I2C_ADDR, I2C_NUM_ROWS, I2C_NUM_COLS)

def on_message(client, userdata, message):
    devices = ['LED', 'TEMPERATURE', 'MOTOR']
    for device in devices:
        if message.topic == f'gpio/{device}':
            if message.payload.decode() == 'ON':     
                if device == 'LED':
                    print('Control test')
                    led.on()
                elif device == 'TEMPERATURE':
                    lcd.putstr("It's working :)")
                elif device == 'MOTOR':
                    motor.forward()
                    sleep(3)
                    motor.stop()
            if message.payload.decode() == 'OFF':
                if device == 'LED':
                    led.off()
                elif device == 'TEMPERATURE':
                    lcd.clear()
                    lcd.move_to(0, 0)
                elif device == 'MOTOR':
                    motor.backward()
                    sleep(3)
                    motor.stop()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(host="raspberry.local")
client.on_message = on_message
client.subscribe("gpio/#")
client.loop_forever()