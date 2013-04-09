#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.
AC_INIT([guestconv], [0.1])
AM_INIT_AUTOMAKE([1.12 foreign -Wno-portability tar-ustar])
AC_CONFIG_SRCDIR(guestconv.c)
#AM_INIT_AUTOMAKE([foreign])
#AM_INIT_AUTOMAKE

AC_CONFIG_SRCDIR([guestconv.c])
AC_CONFIG_HEADERS([config.h])

# Checks for programs.
AC_PROG_CC_C99

LT_INIT([disable-static])

AC_CHECK_HEADERS([unistd.h])

AM_PATH_PYTHON
AC_ARG_VAR([PYTHON_CONFIG], [Path to python-config])
AS_IF([test -z "$PYTHON_CONFIG"], [
  AC_PATH_PROGS([PYTHON_CONFIG],
                [python$PYTHON_VERSION-config python-config],
                [no],
                [`dirname $PYTHON`])
])

AC_ARG_VAR([PYTHON_CFLAGS], [Include flags for python, bypassing python-config])
AS_IF([test -z "$PYTHON_CFLAGS"], [
  AC_MSG_CHECKING([python include flags])
  AS_IF([test "$PYTHON_CONFIG" = no], [AC_MSG_ERROR([cannot find python-config for $PYTHON.])])
  PYTHON_CFLAGS=`$PYTHON_CONFIG --includes`
  AC_MSG_RESULT([$PYTHON_CFLAGS])
])

AC_ARG_VAR([PYTHON_LDADD], [Linker flags for python, bypassing python-config])
AS_IF([test -z "$PYTHON_LDADD"], [
  AC_MSG_CHECKING([python linker flags])
  AS_IF([test "$PYTHON_CONFIG" = no], [AC_MSG_ERROR([cannot find python-config for $PYTHON.])])
  PYTHON_LDADD=`$PYTHON_CONFIG --ldflags`
  AC_MSG_RESULT([$PYTHON_LDADD])
])

AC_CONFIG_FILES([Makefile])
AC_OUTPUT
