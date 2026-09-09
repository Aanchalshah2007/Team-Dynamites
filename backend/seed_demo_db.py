"""Seeds sensors/actuators tables (architecture §1) for the SQL-RAG demo.

Run: python seed_demo_db.py
"""

import sqlite3

from config import DB_PATH

SENSORS = [
    ("DHT22", "temperature_humidity", "-40 to 80 C, 0-100% RH", "3.3-6V", "1-wire digital", "2s"),
    ("HC-SR04", "ultrasonic_distance", "2cm to 400cm", "5V", "digital trigger/echo", "60ms"),
    ("MPU-6050", "imu_accel_gyro", "+-16g, +-2000 deg/s", "3.3-5V", "I2C", "1ms"),
    ("LM35", "temperature", "-55 to 150 C", "4-30V", "analog", "N/A"),
    ("TCS3200", "color", "RGB + clear", "3.3-5V", "digital frequency", "N/A"),
]

ACTUATORS = [
    ("SG90", "servo_motor", "0-180 deg", "4.8-6V", "PWM", "0.1s/60deg"),
    ("NEMA17", "stepper_motor", "1.8 deg/step", "12-24V", "step/dir", "N/A"),
    ("L298N", "motor_driver", "2 channel, up to 2A", "5-35V", "PWM + digital", "N/A"),
    ("SRD-05VDC-SL-C", "relay", "10A @ 250VAC", "5V coil", "digital", "10ms"),
    ("28BYJ-48", "stepper_motor", "5.625/64 deg/step", "5V", "ULN2003 driver", "N/A"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS sensors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sensor_type TEXT NOT NULL,
    measurement_range TEXT,
    operating_voltage TEXT,
    interface TEXT,
    response_time TEXT
);

CREATE TABLE IF NOT EXISTS actuators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    actuator_type TEXT NOT NULL,
    range_or_capacity TEXT,
    operating_voltage TEXT,
    control_interface TEXT,
    response_time TEXT
);
"""


def seed() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM sensors")
        conn.execute("DELETE FROM actuators")
        conn.executemany(
            "INSERT INTO sensors (name, sensor_type, measurement_range, operating_voltage, interface, response_time) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            SENSORS,
        )
        conn.executemany(
            "INSERT INTO actuators (name, actuator_type, range_or_capacity, operating_voltage, control_interface, response_time) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ACTUATORS,
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Seeded {len(SENSORS)} sensors and {len(ACTUATORS)} actuators into {DB_PATH}")


if __name__ == "__main__":
    seed()
