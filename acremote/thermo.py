import glob
import os


class W1Thermo():
    def __init__(self):
        self._DEV_BASE = '/sys/bus/w1/devices'
        self._DEVICES = {
            path.split('/')[-1]: None
            for path in glob.glob(self._DEV_BASE + '/28*')  # Detect DS18B20
        }

    def _read_w1_slave(self, device):
        with open(os.path.join(self._DEV_BASE, device, 'w1_slave')) as file:
            return [line.strip() for line in file.readlines()]

    def poll(self) -> dict:
        for device in self._DEVICES.keys():
            lines = self._read_w1_slave(device)
            while lines[0][-3:] != 'YES':
                lines = self._read_w1_slave(device)

            self._DEVICES[device] = int(lines[1].split('=')[1]) / 1000

        return self._DEVICES


if __name__ == '__main__':
    a = W1Thermo()
    print(a.poll())
