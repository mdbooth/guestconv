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
    guestconv->error = 0;
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
	PyObject *pystr;
	char *str;

	PyErr_Fetch(&ptype, &pvalue, &ptraceback);
        pystr = PyObject_Str(pvalue);
	str = PyString_AsString(pystr);
	gc->error = strdup(str);
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

