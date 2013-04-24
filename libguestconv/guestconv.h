#ifndef __GUESTCONV_H__
#define __GUESTCONV_H__

#include <Python.h>

typedef void (*GuestConvLoggerFunc)(int level, char *message);

typedef struct {
    PyObject *pyth_module;
    PyObject *gc_inst;
    char *error;
    char *error_type;
    char *backtrace;
} GuestConv;


/* logger_func here can be NULL if you don't wish to have any logging callbacks. */
GuestConv *
guestconv_init(char *target, char *database_location, GuestConvLoggerFunc logger_func);

int
guestconv_err(GuestConv *gc);

void
guestconv_add_drive(GuestConv *gc, char *drive);

char *
guestconv_inspect(GuestConv *gc);

void
guestconv_convert(GuestConv *gc, char *description);

#endif
