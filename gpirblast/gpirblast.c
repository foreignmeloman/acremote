#include <Python.h>
#include "irslinger.h"

static char helloworld_docs[] = "helloworld method docstring\n";
static PyObject *helloworld(PyObject *self, PyObject *args)
{
	return Py_BuildValue("s", "Hello, Python 3 extensions!!");
	// Py_RETURN_NONE;
}


static char sendCode_docs[] = "sendCode method docstring\n";
static PyObject *sendCode(PyObject *self, PyObject *args)  // TODO add kwargs
{
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
	char *code;                      // The string contining the ir code in binary format

	if (!PyArg_ParseTuple(args, "is", &outPin, &code)) {
		return NULL;
	}
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
		code);

	return Py_BuildValue("i", result);
}


static PyMethodDef module_methods[] = {
	{ "hello_world", (PyCFunction) helloworld, METH_NOARGS, helloworld_docs},
	{ "send_code", (PyCFunction) sendCode, METH_VARARGS, sendCode_docs},
	{NULL}
};

static char gpirblast_docs[] = "gpirblast module docstring\n";
static struct PyModuleDef gpirblast = {
	PyModuleDef_HEAD_INIT,
	"gpirblast", /* name of module */
	gpirblast_docs,
	-1, /* size of per-interpreter state of the module, or -1 if the module keeps state in global variables. */
	module_methods
};

PyMODINIT_FUNC PyInit_gpirblast(void)
{
	return PyModule_Create(&gpirblast);
}