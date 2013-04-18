# Contribution Guidelines 

## Python Style Conventions

* Adhere to PEP 8 (http://www.python.org/dev/peps/pep-0008/), which include:
 * 4 spaces per indentation level.
 * Maximum line length of 79 charachters.
 * And much more.  Read it!

## Text Encoding

Always use unicode when defining strings in code.  For example,

    >>> msg = u'hello'

is acceptable.  A plain-old 'hello' is not.

## Documentation

* Docstrings
 * Adhere to PEP 257 (http://www.python.org/dev/peps/pep-0257/).
 * Follow the sphinx syntax for describing parameters, return values
   and exceptions.

## Internationalisation

All strings which might be displayed to an end user must be translated.
This includes:

* exceptions with information interesting to the end user (e.g. ConversionError)
* all log messages of INFO level and above

Strings which are only relevant to the developer should not be translated. This
includes:

* exceptions indicating a programming error
* all debug log messages

If a module uses translated strings, it must include the following in its import
declarations:

  from guestconv.lang import _

An example of a simple translation is:

  _(u'This is a simple translation')

If a string includes substitutions, these must substituted by name. This helps
translators in a couple of ways: it gives them an indication of what is being
substituted, and it allows them to re-order the substitutions. For example:

  _(u'Error in %(name) module: %(msg)') % {u'name': module, u'msg': msg}

Note the following potential traps when making translatable strings:

* translation must be done on the string before substitutions
* translated strings may not contain a concatenation, e.g. _(u'foo ' + u'bar')
* translated strings must not contain trailing newlines
