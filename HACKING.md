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

## String formatting and internationalisation

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

All string substitutions must use string.format(), and must substitute by name.
This helps translators in a couple of ways: it gives them an indication of what
is being substituted, and it allows them to re-order the substitutions. For
example:

  _(u'Error in {name} module: {msg}').format(name=module, msg=msg)

Note the following potential traps when making translatable strings:

* translation must be done on the string before substitutions
* translated strings must be string constants
    String constants can still be split across multiple lines for line length or
    clearer formatting:
        _(u'This is a string '
          u'broken across 2 lines')
* translated strings must not contain trailing newlines
    Newlines can be added afterwards:
        _('A translated error: {msg}').format(msg=msg) + u'\n'
