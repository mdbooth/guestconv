#include "guestconv.h"
#include <stdio.h>
#include <string.h>

static GuestConvLoggerFunc guestconv_logger_func = NULL;

/* First step is to set up a logging callback so we can get info
   back to the user. */
static PyObject *
libconv_log(PyObject *self, PyObject *args)
{
    int loglvl;
    char *logstr;

    if (guestconv_logger_func == NULL) {
        return Py_BuildValue("i", 0);
    }

    if (!PyArg_ParseTuple(args, "is", &loglvl, &logstr)) {
        fprintf(stderr, "Unable to parse logging arguments.\n");
        return Py_BuildValue("i", 0);
    }

    guestconv_logger_func(loglvl, logstr);

    return Py_BuildValue("i", 0);
}

static PyMethodDef LibconvLogMethods[] = {
    {"libconv_log",  libconv_log, METH_VARARGS, "Log a message."},
    {NULL, NULL, 0, NULL}
};

/* initialize the module and return the logging function defined above */
static PyObject *
guestconv_get_local_log_func(void)
{
    PyObject *log_module;
    PyObject *log_func;

    // Initialize the guestconv logging method which we will define
    // in C so we can recieve messages from guestconv.
    log_module = Py_InitModule("LibconvLog", LibconvLogMethods);
    if (log_module == NULL) {
        return NULL;
    }
    log_func = PyObject_GetAttrString(log_module, "libconv_log");

    return log_func;
}


/* Allocate and zero a new guestconv struct */
static GuestConv *
guestconv_new(void)
{
    GuestConv *guestconv;

    guestconv = malloc(sizeof(GuestConv));
    if (guestconv == NULL) {
        fprintf(stderr, "Unable to allocate memory for guestconv structure.\n");
        return NULL;
    }
    guestconv->error = NULL;
    guestconv->error_type = NULL;
    guestconv->backtrace = NULL;
    guestconv->pyth_module = NULL;
    guestconv->gc_inst = NULL;

    return guestconv;
}


/* Check for a python error and go through all kinds of hoops to get
   good information about what has gone wrong. */
static void
guestconv_check_pyerr(GuestConv *gc)
{
    PyObject *err;

    err = PyErr_Occurred();
    if (err != NULL) {
        PyObject *ptype, *pvalue, *ptraceback;
        PyObject *pystr, *module_name, *pyth_module, *pyth_func;
        char *str;

        PyErr_Fetch(&ptype, &pvalue, &ptraceback);
        pystr = PyObject_Str(pvalue);
        str = PyString_AsString(pystr);
        gc->error = strdup(str);

        pystr = PyObject_GetAttrString(ptype, "__name__");
        str = PyString_AsString(pystr);
        gc->error_type = strdup(str);

        /* See if we can get a full traceback */
        module_name = PyString_FromString("traceback");
        pyth_module = PyImport_Import(module_name);
        Py_DECREF(module_name);

        if (pyth_module == NULL) {
            gc->backtrace = "Cannot load python module 'traceback'";
            return;
        }

        pyth_func = PyObject_GetAttrString(pyth_module, "format_exception");
        if (pyth_func && PyCallable_Check(pyth_func)) {
            PyObject *pyth_val;

            pyth_val = PyObject_CallFunctionObjArgs(pyth_func, ptype, pvalue, ptraceback, NULL);

            pystr = PyObject_Str(pyth_val);
            str = PyString_AsString(pystr);
            gc->backtrace = strdup(str);
        }
    }
}


int
guestconv_err(GuestConv *gc)
{
    return gc->error != NULL;
}


/* Load the python guestconv module and call the init
   method all the while doing loads of error checking. */
GuestConv *
guestconv_init(char *target, char *database_location, GuestConvLoggerFunc logger_func)
{
    PyObject *module_name, *pyth_module, *pyth_func;
    PyObject *pyth_val;
    PyObject *local_log_func;
    GuestConv *gc = NULL;

    gc = guestconv_new();
    if (gc == NULL)
        return gc;

    guestconv_logger_func = logger_func;

    Py_Initialize();
    module_name = PyString_FromString("guestconv");

    pyth_module = PyImport_Import(module_name);
    Py_DECREF(module_name);

    if (pyth_module == NULL) {
        gc->error = "Cannot load python module 'guestconv'";
        return gc;
    }

    gc->pyth_module = pyth_module;

    local_log_func = guestconv_get_local_log_func();

    pyth_func = PyObject_GetAttrString(pyth_module, "Converter");

    if (pyth_func && PyCallable_Check(pyth_func)) {
        pyth_val = PyObject_CallFunction(pyth_func, "s[s]O", target, database_location, local_log_func);

        if (pyth_val != NULL) {
            gc->gc_inst = pyth_val;
        } else {
            Py_DECREF(pyth_func);
            Py_DECREF(pyth_module);
            guestconv_check_pyerr(gc);
            return gc;
        }
    } else {
        guestconv_check_pyerr(gc);
    }

    return gc;
}

void
guestconv_add_drive(GuestConv *gc, char *drive)
{
    if (gc->gc_inst == NULL) {
        gc->error = "guestconv instance was never initialized.";
        return;
    }

    PyObject_CallMethod(gc->gc_inst, "add_drive", "s", drive);
    guestconv_check_pyerr(gc);
}

char *
guestconv_inspect(GuestConv *gc)
{
    PyObject *ret;
    char *str = NULL;

    if (gc->gc_inst == NULL) {
        gc->error = "guestconv instance was never initialized.";
        return NULL;
    }

    ret = PyObject_CallMethod(gc->gc_inst, "inspect", NULL);
    guestconv_check_pyerr(gc);

    if (!guestconv_err(gc))
        str = PyString_AsString(ret);

    return str;
}

void
guestconv_convert(GuestConv *gc, char *description)
{
    if (gc->gc_inst == NULL) {
        gc->error = "guestconv instance was never initialized.";
        return;
    }

    PyObject_CallMethod(gc->gc_inst, "convert", "s", description);
    guestconv_check_pyerr(gc);
}

