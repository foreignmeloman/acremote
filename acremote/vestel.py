# Based on Vestel YKR-H/002E AC remote
from time import sleep
from acremote.thermo import W1Thermo

import gpirblast


class VestelACRemote():

    def __init__(self, gpio_pin: int):
        self._SWING = True
        self._ON = False
        self._HEALTH = False
        self._STRONG = False
        self._SLEEP = False
        self._TIMER = 0.0
        self._SCREEN = True
        self._CLEAN = False
        self._FRESH = False
        self._FEELING = False
        self._TEMP = 27
        self._MIN_TEMP = 16
        self._MAX_TEMP = 36
        self._MODES = {
            'AUTO': 0,
            'COOL': 32,
            'DRY': 64,
            'HEAT': 128,
            'FAN': 192,
        }
        self._MODE = 'COOL'
        self._SPEEDS = {
            'AUTO': 160,
            'LOW': 96,
            'MID': 64,
            'HIGH': 32,
        }
        self._SPEED = 'HIGH'
        self._GPIO_PIN = gpio_pin
        self._THERMO = W1Thermo()
        self._DATA_FIELDS = [
            195,   # 00 Device ID 0
            0,     # 01 Temperature value from 64 to 192 (step=8) +7 if SWING=off
            224,   # 02 Device ID 1
            0,     # 03 Unknown value
            0,     # 04 SPEED + TIMER integral part (in hours)
            0,     # 05 TIMER fractional part (30 in minutes) + STRONG switch (+/-64)
            0,     # 06 MODE, FRESH (+/-16), FEELING switch (+/-8), SLEEP (+/-4)
            0,     # 07 FEELING value +74 +ROOM_TEMP in Celsius (AC Remote value)
            0,     # 08 Unknown value
            0,     # 09 ON/OFF (0/32), health (+/-2 works only when on), TIMER on +64
            0,     # 10 Unknown value
            0,     # 11 Button ID
        ]

    #################################################
    # PROPERTIES
    #################################################
    @property
    def swing(self) -> bool:
        return self._SWING

    @swing.setter
    def swing(self, value: bool):
        if isinstance(value, bool):
            self._SWING = value
        else:
            raise ValueError('Swing value must be a boolean')

    @property
    def on(self) -> bool:
        return self._ON

    @on.setter
    def on(self, value: bool):
        if isinstance(value, bool):
            self._ON = value
        else:
            raise ValueError('On value must be a boolean')

    @property
    def health(self) -> bool:
        return self._HEALTH

    @health.setter
    def health(self, value: bool):
        if isinstance(value, bool):
            self._HEALTH = value
        else:
            raise ValueError('Health value must be a boolean')

    @property
    def strong(self) -> bool:
        return self._STRONG

    @strong.setter
    def strong(self, value: bool):
        if isinstance(value, bool):
            self._STRONG = value
        else:
            raise ValueError('Strong value must be a boolean')

    @property
    def sleep(self) -> bool:
        return self._SLEEP

    @sleep.setter
    def sleep(self, value: bool):
        if isinstance(value, bool):
            self._SLEEP = value
        else:
            raise ValueError('Sleep value must be a boolean')

    @property
    def screen(self) -> bool:
        return self._SCREEN

    @screen.setter
    def screen(self, value: bool):
        if isinstance(value, bool):
            self._SCREEN = value
        else:
            raise ValueError('Screen value must be a boolean')

    @property
    def clean(self) -> bool:
        return self._CLEAN

    @clean.setter
    def clean(self, value: bool):
        if isinstance(value, bool):
            self._CLEAN = value
        else:
            raise ValueError('Clean value must be a boolean')

    @property
    def fresh(self) -> bool:
        return self._FRESH

    @fresh.setter
    def fresh(self, value: bool):
        if isinstance(value, bool):
            self._FRESH = value
        else:
            raise ValueError('Fresh value must be a boolean')

    @property
    def feeling(self) -> bool:
        return self._FEELING

    @feeling.setter
    def feeling(self, value: bool):
        if isinstance(value, bool):
            self._FEELING = value
        else:
            raise ValueError('Feeling value must be a boolean')

    @property
    def temp(self) -> int:
        return self._TEMP

    @temp.setter
    def temp(self, value: int):
        if value in range(self._MIN_TEMP, self._MAX_TEMP + 1):
            self._TEMP = int(value)
        else:
            raise ValueError(
                'Temperature value must be within {} and {}'.format(
                    self._MIN_TEMP, self._MAX_TEMP
                )
            )

    @property
    def min_temp(self):
        return self._MIN_TEMP

    @property
    def max_temp(self):
        return self._MAX_TEMP

    @property
    def mode(self):
        return self._MODE

    @mode.setter
    def mode(self, value: str):
        if value in self._MODES:
            self._MODE = value
        else:
            raise ValueError('Mode value must be in {}'.format(self._MODES))

    @property
    def speed(self) -> str:
        return self._SPEED

    @speed.setter
    def speed(self, value: str):
        if value in self._SPEEDS:
            self._SPEED = value
        else:
            raise ValueError('Speed value must be in {}'.format(self._SPEEDS))

    @property
    def timer(self) -> float:
        return self._TIMER

    @timer.setter
    def timer(self, value: float):
        error = 'Timer value must be within 0 and 24'
        try:
            value = float(value)
        except ValueError:
            raise ValueError(error)

        if 0.0 <= value <= 24.0:
            if value % 0.5 == 0.0:
                self._TIMER = value
            else:
                self._TIMER = float(int(value))  # cut out the fractional part
        else:
            self._TIMER = 0.0
            raise ValueError(error)

    # Dynamic property
    def timer_step(self, timer: float) -> float:
        if not timer:
            timer = self._TIMER

        step = 0.5
        if 10.0 <= timer < 24.0:
            step = 1.0

        return step

    #################################################
    # STATIC METHODS
    #################################################

    @staticmethod
    def form_octet(value: int):
        string = bin(value)[2:]  # remove '0b'
        length = len(string)
        if length < 8:
            string = '0' * (8 - length) + string

        if length > 8:
            string = string[-8:]  # overflow

        return string

    #################################################
    # INTERNAL METHODS
    #################################################

    def _set_on_off(self):
        if self._ON:
            self._CLEAN = False
            self._DATA_FIELDS[9] = 32
            if self._HEALTH:
                self._DATA_FIELDS[9] += 2
            if self._TIMER != 0.0:
                self._DATA_FIELDS[9] += 64
        else:
            if self._CLEAN:
                self._DATA_FIELDS[9] = 4
            else:
                self._DATA_FIELDS[9] = 0

    def _set_mode_fresh_feeling_sleep(self):
        self._DATA_FIELDS[6] = self._MODES[self._MODE]

        if self._FRESH:
            self._DATA_FIELDS[6] += 16

        if self._FEELING:
            self._DATA_FIELDS[6] += 8
            self._DATA_FIELDS[6] = 74 + int(list(self._THERMO.poll().values())[0])
        else:
            self._DATA_FIELDS[7] = 0

        if self._SLEEP:
            self._DATA_FIELDS[6] += 4

    def _set_temp_and_swing(self):
        if self._MODE in ('AUTO', 'FAN'):
            self._DATA_FIELDS[1] = 0
        else:
            self._DATA_FIELDS[1] = 64 + ((self._TEMP - self._MIN_TEMP) * 8)

        if not self._SWING:
            self._DATA_FIELDS[1] += 7

    def _set_speed_and_timer_int(self):
        if self._MODE == 'AUTO':
            self._SPEED = self._MODE

        self._DATA_FIELDS[4] = self._SPEEDS[self._SPEED]

        self._DATA_FIELDS[4] += int(self._TIMER)  # timer hours

    def _set_strong_and_timer_frac(self):
        if self._STRONG:
            self._DATA_FIELDS[5] = 64
        else:
            self._DATA_FIELDS[5] = 0

        if self._TIMER % 1 == 0.5:
            self._DATA_FIELDS[5] += 30  # timer minutes

    def _form_bin_str(self):
        bin_str = ''
        chk_sum = 0
        for value in self._DATA_FIELDS:
            chk_sum += value
            bin_str += self.form_octet(value)[::-1]  # reverse octet to form a proper signal
            # print(self.form_octet(value)[::-1], value)

        # print(self.form_octet(chk_sum)[::-1], int(self.form_octet(chk_sum)[::-1], 2))
        bin_str += self.form_octet(chk_sum)[::-1]
        return bin_str

    def _refresh_data_fields(self):
        self._set_on_off()
        self._set_mode_fresh_feeling_sleep()
        self._set_temp_and_swing()
        self._set_speed_and_timer_int()
        self._set_strong_and_timer_frac()

    def _send_code(self):
        self._refresh_data_fields()
        gpirblast.send_code(self._GPIO_PIN, self._form_bin_str())

    #################################################
    # BUTTONS
    #################################################

    def btn_on(self):
        # Virtual button
        self._ON = False
        self.btn_on_off()

    def btn_off(self):
        # Virtual button
        self._ON = True
        self.btn_on_off()

    def btn_tmp_set(self, value: int) -> bool:
        # Virtual button
        self._DATA_FIELDS[9] = 32
        self._DATA_FIELDS[11] = 5
        self._ON = True
        # act_allow = value in range(self._MIN_TEMP, self._MAX_TEMP + 1)
        # if act_allow:
        #     self._TEMP = value
        try:
            self.temp = int(value)
        except ValueError:
            raise ValueError('Temperature value must be within 16 and 32')

        self._send_code()
        # return act_allow

    def btn_fungusproof(self):
        # Button ID = NONE
        if not self._ON:
            self._ON = True  # Force turn off
            self.btn_on_off()
            sleep(1)
            self._ON = True
            self.btn_on_off()
            sleep(1)
            self._ON = True
            self.btn_on_off()

    def btn_tmp_up(self) -> bool:
        # Button ID = 0
        act_allow = self._TEMP < self._MAX_TEMP
        if act_allow:
            self._TEMP += 1
        else:
            self._TEMP = self._MAX_TEMP

        if self._ON:
            self._DATA_FIELDS[11] = 0
            self._send_code()

        return act_allow

    def btn_tmp_down(self) -> bool:
        # Button ID = 1
        act_allow = self._TEMP > self._MIN_TEMP
        if act_allow:
            self._TEMP -= 1
        else:
            self._TEMP = self._MIN_TEMP

        if self._ON:
            self._DATA_FIELDS[11] = 1
            self._send_code()

        return act_allow

    def btn_swing(self):
        # Button ID = 2
        if self._ON:
            self._DATA_FIELDS[11] = 2
            self._SWING = not self._SWING
            self._send_code()

    def btn_speed(self, value: str):
        # Button ID = 4
        if self._ON:
            self._DATA_FIELDS[11] = 4
            self.speed = value.upper()
            self._send_code()

    def btn_on_off(self):
        # Button ID = 5
        self._DATA_FIELDS[11] = 5
        self._ON = not self._ON
        self._send_code()

    def btn_mode(self, value: str):
        # Button ID = 6
        if self._ON:
            self._DATA_FIELDS[11] = 6
            self.mode = value.upper()
            self._send_code()

    def btn_health(self):
        # Button ID = 7
        if self._ON:
            self._DATA_FIELDS[11] = 7
            self._HEALTH = not self._HEALTH
            self._send_code()

    def btn_strong(self):
        # Button ID = 8
        if self._ON:
            self._DATA_FIELDS[11] = 8
            self._STRONG = not self._STRONG
            self._send_code()

    def btn_sleep(self):
        # Button ID = 11
        if self._ON:
            self._DATA_FIELDS[11] = 11
            self._SLEEP = not self._SLEEP
            self._send_code()

    def btn_timer(self, value=0.0):
        # Button ID = 13
        if self._ON:
            self._DATA_FIELDS[11] = 13
            self.timer = value
            self._send_code()

    def btn_screen(self):
        # Button ID = 21
        if self._ON:
            self._DATA_FIELDS[11] = 21
            self._SCREEN = not self._SCREEN
            self._send_code()

    def btn_clean(self):
        # Button ID = 25
        if self._ON:
            return False
        else:
            self._DATA_FIELDS[11] = 25
            self._CLEAN = not self._CLEAN
            self._send_code()
            return True

    def btn_fresh(self):
        # Button ID = 29
        if self._ON:
            self._DATA_FIELDS[11] = 29
            self._FRESH = not self._FRESH
            self._send_code()

    def btn_feeling(self):
        # Button ID = 30
        if self._ON:
            self._DATA_FIELDS[11] = 30
            self._FEELING = not self._FEELING
            self._send_code()


if __name__ == '__main__':
    a = VestelACRemote()
    a.btn_on_off()
