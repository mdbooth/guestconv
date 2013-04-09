#include "guestconv.h"
#include <stdio.h>
#include <string.h>

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
}

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
            Py_DECREF(pyth_val);
        }
    }
}


int
guestconv_err(GuestConv *gc)
{
    return gc->error != NULL;
}

GuestConv *
guestconv_init(char *database_location)
{
    PyObject *module_name, *pyth_module, *pyth_func;
    PyObject *python_tuple, *pyth_val;
    GuestConv *gc = NULL;
    int i;

    gc = guestconv_new();
    if (gc == NULL)
	return gc;

    Py_Initialize();
    module_name = PyString_FromString("guestconv");
    /* Error checking of module_name left out */

    pyth_module = PyImport_Import(module_name);
    Py_DECREF(module_name);

    if (pyth_module == NULL) {
	gc->error = "Cannot load python module 'guestconv'";
	return gc;
    }

    gc->pyth_module = pyth_module;

    pyth_func = PyObject_GetAttrString(pyth_module, "Converter");
    /* pyth_func is a new reference */

    if (pyth_func && PyCallable_Check(pyth_func)) {
        pyth_val = PyObject_CallFunction(pyth_func, "[s]", "/home/imain/src/guestconv/conf/guestconv.db");

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
guestconv_inspect(GuestConv *gc, char *target)
{
    PyObject *ret;
    char *str = NULL;

    if (gc->gc_inst == NULL) {
        gc->error = "guestconv instance was never initialized.";
        return NULL;
    }

    ret = PyObject_CallMethod(gc->gc_inst, "inspect", "s", target);
    guestconv_check_pyerr(gc);

    if (!guestconv_err(gc))
	str = PyString_AsString(ret);

    return str;
}

void
guestconv_convert(GuestConv *gc, char *description)
{
    PyObject *ret;
    char *str = NULL;

    if (gc->gc_inst == NULL) {
        gc->error = "guestconv instance was never initialized.";
        return;
    }

    PyObject_CallMethod(gc->gc_inst, "convert", "s", description);
    guestconv_check_pyerr(gc);
}

