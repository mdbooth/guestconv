# Contribution Guidelines 

## Python Style Conventions

* Adhere to PEP 8 (http://www.python.org/dev/peps/pep-0008/), which include:
** 4 spaces per indentation level.
** Maximum line length of 79 charachters.
** And much more.  Read it!

## Text Encoding

Always use unicode when defining strings in code.  For example,

    >>> msg = u'hello'

is acceptable.  A plain-old 'hello' is not.

## Documentation

* Docstrings
** Adhere to PEP 257 (http://www.python.org/dev/peps/pep-0257/).
** Follow the sphinx syntax for describing parameters, return values
   and exceptions.
