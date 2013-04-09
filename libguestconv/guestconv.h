#ifndef __GUESTCONV_H__
#define __GUESTCONV_H__

#include <Python.h>

typedef struct {
    PyObject *pyth_module;
    PyObject *gc_inst;
    char *error;
    char *error_type;
    char *backtrace;
} GuestConv;

GuestConv *
guestconv_init(char *database_location);

int
guestconv_err(GuestConv *gc);

void
guestconv_add_drive(GuestConv *gc, char *drive);

char *
guestconv_inspect(GuestConv *gc, char *target);

void
guestconv_convert(GuestConv *gc, char *description);

#endif
