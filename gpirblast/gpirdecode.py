#!/usr/bin/env python3
import RPi.GPIO as GPIO
from datetime import datetime
from time import sleep

# This is for revision 1 of the Raspberry Pi, Model B
# This pin is also referred to as GPIO23 (PIN16)
INPUT_PIN = 23

GPIO.setmode(GPIO.BCM)
GPIO.setup(INPUT_PIN, GPIO.IN)

while True:
    value = 1
    # Loop until we read a 0
    while value:
        value = GPIO.input(INPUT_PIN)

    # Grab the start time of the command
    start_time = datetime.now()

    # Used to buffer the command pulses
    command = []

    # The end of the "command" happens when we read more than
    # a certain number of 1s (1 is off for my IR receiver)
    inactive_count = 0

    # Used to keep track of transitions from 1 to 0
    previous_value = 0

    while True:

        if value != previous_value:
            # The value has changed, so calculate the length of this run
            now = datetime.now()
            pulse_length = now - start_time
            start_time = now

            command.append((previous_value, pulse_length.microseconds))

        if value:
            inactive_count = inactive_count + 1
        else:
            inactive_count = 0

        # 10000 is arbitrary, adjust as necessary
        if inactive_count > 10000:
            break

        previous_value = value
        value = GPIO.input(INPUT_PIN)

    # print('------RAW-DATA-START-----')
    # for i in command:
    #     print(i[0], i[1])
    # print("-------RAW-DATA-END------\n")

    # print("Size of array is " + str(len(command)))

    # Check if the command starts with 9000µs pulse and 4500µs pause
    try:
        ratio = round(command[0][1] / command[1][1])
    except IndexError:
        continue

    # NEC or Samsung
    if ratio in (1, 2):
        command.pop(0)
        command.pop(0)
        binaryString = ''.join(
            map(lambda x: '1' if x[1] > 1000 else '0',
                filter(lambda x: x[0] == 1, command))
        )
        if len(binaryString) % 8 == 0:
            print('RATIO: ', ratio)
            print('BIN: ', binaryString)
            print('--COMMAND-START--')
            # print('bin     \tdec     \trevbin  \trevdec')
            print('bin  \t\tdec')
            checksum_dec = 0
            for i in range(int(len(binaryString) / 8)):
                octet = binaryString[i * 8:i * 8 + 8]
                rev_bin = octet[::-1]
                rev_dec = int(octet[::-1], 2)
                checksum_dec += rev_dec
                # print('{}\t{}\t\t{}\t{}'.format(octet, int(octet, 2), octet[::-1], int(octet[::-1], 2)))
                print('{}\t{}'.format(rev_bin, rev_dec))  # TODO add --verbose option to enable this
            checksum_dec -= rev_dec  # we don't need the last value
            checksum_bin = bin(checksum_dec)[-8:]  # we need only last 8 bits of the checksum
            if checksum_bin == rev_bin:
                print('{} <- AC CHECKSUM MATCH'.format(checksum_bin))
            else:
                print('{} <- AC CHECKSUM MISMATCH'.format(checksum_bin))
            print('--COMMAND-END----\n')
        else:
            print('ERROR: "{}" lenght must be multiple of 8. Try again.'.format(binaryString))
    else:
        print('ERROR: Invalid beggining sequence for NEC IR protocol.')
    sleep(0.5)  # sleep for 0.5 second to prevent false positive triggering
