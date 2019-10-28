#include <stdio.h>
#include <stdlib.h>
#include "irslinger.h"

void usage(char exe_name[]);

int main(int argc, char *argv[]) {

	// Default values
	uint32_t outPin;                 // The Broadcom (GPIO) pin number the signal will be sent on
	int frequency = 38000;           // The frequency of the IR signal in Hz
	double dutyCycle = 0.5;          // The duty cycle of the IR signal. 0.5 means for every cycle,
	                                 // the LED will turn on for half the cycle time, and off the other half
	int leadingPulseDuration = 9000; // The duration of the beginning pulse in microseconds
	int leadingGapDuration = 4500;   // The duration of the gap in microseconds after the leading pulse
	int onePulse = 562;              // The duration of a pulse in microseconds when sending a logical 1
	int zeroPulse = 562;             // The duration of a pulse in microseconds when sending a logical 0
	int oneGap = 1688;               // The duration of the gap in microseconds when sending a logical 1
	int zeroGap = 562;               // The duration of the gap in microseconds when sending a logical 0
	int sendTrailingPulse = 1;       // 1 = Send a trailing pulse with duration equal to "onePulse"
	                                 // 0 = Don't send a trailing pulse

	if (argc < 3) {
		fprintf(stderr, "%s\n", "ERROR: Missing necessary arguments");
		usage(argv[0]);
		return 1;
	}
	else {
		outPin = atoi(argv[1]);
	}
	if (argc == 4) leadingPulseDuration = atoi(argv[3]);
	if (argc == 5) leadingGapDuration = atoi(argv[4]);

	int result = irSling(
		outPin,
		frequency,
		dutyCycle,
		leadingPulseDuration,
		leadingGapDuration,
		onePulse,
		zeroPulse,
		oneGap,
		zeroGap,
		sendTrailingPulse,
		argv[2]);
	
	return result;
}

void usage(char exe_name[]) {
	char* usage_str =
		"\nUsage: %s PIN CODE [LPD] [LGD]\n\n"
		"\tPIN\t- GPIO pin to use\n"
		"\tCODE\t- raw binary code\n"
		"\tLPD\t- duration of the beginning pulse in microseconds\n"
		"\tLGD\t- duration of the gap in microseconds after the leading pulse\n";
	printf(usage_str, exe_name);
}

