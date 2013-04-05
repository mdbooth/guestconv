noinst_PROGRAMS = test

test_CXXFLAGS=-O0 -g
test_SOURCES = test.c
test_CFLAGS = $(PYTHON_CFLAGS)
test_LDADD = $(PYTHON_LDADD) -lguestconv

lib_LTLIBRARIES = libguestconv.la

libguestconv_la_SOURCES = guestconv.c guestconv.h
libguestconv_la_CFLAGS = $(PYTHON_CFLAGS)
libguestconv_la_LIBADD = $(PYTHON_LDADD)

