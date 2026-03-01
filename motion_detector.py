"""
motion_detector.py
Thread-safe motion detector using MPU6050.
API: detector.is_moving() → bool
"""

from mpu6050 import mpu6050
import time
import math
from collections import deque
import threading
from typing import Optional, Dict   # ← добавили Optional


class MotionDetector:
    """Detects motion using accelerometer delta and gyroscope magnitude."""

    def __init__(self):
        self.sensor = mpu6050(0x68)

        # Tunable thresholds
        self.ACCEL_DELTA_THRESHOLD = 0.05   # g
        self.GYRO_THRESHOLD = 10.0          # deg/s
        self.SMOOTHING_WINDOW = 10          # samples

        self.accel_bias, self.gyro_bias = self._calibrate_sensor()

        self._is_moving = False
        self._lock = threading.Lock()

        self._thread = threading.Thread(target=self._monitor_motion, daemon=True)
        self._thread.start()

    # --------------------------------------------------------------------- #
    # Calibration
    # --------------------------------------------------------------------- #
    def _calibrate_sensor(self, samples: int = 500):
        print("Calibrating sensor... Keep the device still!")
        accel_sum: Dict[str, float] = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        gyro_sum:  Dict[str, float] = {'x': 0.0, 'y': 0.0, 'z': 0.0}

        for i in range(samples):
            accel = self.sensor.get_accel_data()
            gyro  = self.sensor.get_gyro_data()
            for axis in ['x', 'y', 'z']:
                accel_sum[axis] += accel[axis]
                gyro_sum[axis]  += gyro[axis]
            time.sleep(0.01)

        for axis in ['x', 'y', 'z']:
            accel_sum[axis] /= samples
            gyro_sum[axis]  /= samples

        print("Calibration complete")
        return accel_sum, gyro_sum

    # --------------------------------------------------------------------- #
    # Helper math
    # --------------------------------------------------------------------- #
    @staticmethod
    def _total_vector(data: Dict[str, float]) -> float:
        return math.sqrt(data['x']**2 + data['y']**2 + data['z']**2)

    @staticmethod
    def _smooth(data: Dict[str, float], buffer: deque, window_size: int) -> Dict[str, float]:
        buffer.append(data)
        # Keep only last N samples
        if len(buffer) > window_size:
            buffer.popleft()
        avg = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        for axis in ['x', 'y', 'z']:
            avg[axis] = sum(d[axis] for d in buffer) / len(buffer)
        return avg

    @staticmethod
    def _delta(current: Dict[str, float],
               previous: Optional[Dict[str, float]]) -> float:
        """Return Euclidean distance between two accel vectors."""
        if previous is None:
            return 0.0
        return math.sqrt(
            (current['x'] - previous['x'])**2 +
            (current['y'] - previous['y'])**2 +
            (current['z'] - previous['z'])**2
        )

    # --------------------------------------------------------------------- #
    # Background thread
    # --------------------------------------------------------------------- #
    def _monitor_motion(self):
        buffer = deque(maxlen=self.SMOOTHING_WINDOW)
        prev_accel: Optional[Dict[str, float]] = None

        while True:
            raw_accel = self.sensor.get_accel_data()
            raw_gyro  = self.sensor.get_gyro_data()

            smooth_accel = self._smooth(raw_accel, buffer, self.SMOOTHING_WINDOW)

            accel = {
                ax: smooth_accel[ax] - self.accel_bias[ax]
                for ax in ['x', 'y', 'z']
            }
            gyro = {
                ax: raw_gyro[ax] - self.gyro_bias[ax]
                for ax in ['x', 'y', 'z']
            }

            accel_delta = self._delta(accel, prev_accel)
            gyro_mag    = self._total_vector(gyro)

            moving = (accel_delta > self.ACCEL_DELTA_THRESHOLD) or (gyro_mag > self.GYRO_THRESHOLD)

            with self._lock:
                self._is_moving = moving

            prev_accel = accel.copy()
            time.sleep(0.1)

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def is_moving(self) -> bool:
        """True if motion was detected since last call; resets the flag."""
        with self._lock:
            was_moving = self._is_moving
            self._is_moving = False
            return was_moving
