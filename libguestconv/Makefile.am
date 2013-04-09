noinst_PROGRAMS = example

example_SOURCES = example.c
example_CFLAGS = $(PYTHON_CFLAGS)
example_LDADD = $(PYTHON_LDADD) -lguestconv

lib_LTLIBRARIES = libguestconv.la

libguestconv_la_SOURCES = guestconv.c guestconv.h
libguestconv_la_CFLAGS = $(PYTHON_CFLAGS)
libguestconv_la_LIBADD = $(PYTHON_LDADD)

