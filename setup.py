#!/usr/bin/env python3

from setuptools import setup


setup(
      name='latexmake',
      version='0.5dev',
      description=('Latexmake completely automates the process of '
                   'generating a LaTeX document.'),
      long_description=('Latexmk.py completely automates the process of '
                        'generating a LaTeX document. Given the source files '
                        'for a document, latexmk.py issues the appropriate '
                        'sequence of commands to generate a .dvi or .pdf '
                        'version of the document. Latexmk.py can also watch '
                        'source files for changes and rebuild automatically '
                        'when changes happen.'),
      author='Jan Kanis',
      author_email='jan.code@jankanis.nl',
      url='http://bitbucket.org/JanKanis/latexmake',
      license='GPLv3+',
      platforms='any',
      classifiers=['Development Status :: 4 - Beta',
                   'Intended Audience :: End Users/Desktop',
                   'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Topic :: Printing',
                   'Topic :: Text Processing :: Markup :: LaTeX'],

      py_modules=['latexmake'],
      entry_points={'console_scripts': ['latexmake = latexmake:main']},
      )
