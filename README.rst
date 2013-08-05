latexmake.py
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

URL: http://bitbucket.org/JanKanis/latexmake/

Latexmk.py was originally written by Marc Schlaich. His (now unmaintained)
version is available at https://github.com/schlamar/latexmk.py

Inspired by http://ctan.tug.org/tex-archive/support/latexmk/


Installation
------------

Preferable via pip::

    pip install latexmake

For source installation you need
`distribute <http://pypi.python.org/pypi/distribute>`_ or
`setuptools <http://pypi.python.org/pypi/setuptools>`_


Usage
-----

::

    $ latexmake [options] [filename]

For details run::

    $ latexmake -h


License
-------

GPL version 3 or later.
