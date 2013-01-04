latexmk.py
==========

Overview
--------

Latexmake completely automates the process of generating
a LaTeX document. Given the source files for a document,
latexmake issues the appropriate sequence of commands to
generate a .dvi or .pdf version of the document.
Latexmake can run as a custom builder for the Eclipse-Plugin 
"Texlipse". Latexmake also has the ability to run in the 
background watching source files for changes and rebuilding 
a project when changes happen. 

Based on latexmk.py at https://github.com/schlamar/latexmk.py

Inspired by http://ctan.tug.org/tex-archive/support/latexmk/


Installation
------------

Preferable via pip::

    pip install latexmk.py

For source installation you need
`distribute <http://pypi.python.org/pypi/distribute>`_ or
`setuptools <http://pypi.python.org/pypi/setuptools>`_


Usage
-----

::

    $ latexmk.py [options] [filename]

For details run::

    $ latexmk.py -h


License
-------

GPL version 3 or later.
