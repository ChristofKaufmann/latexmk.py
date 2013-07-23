#!/usr/bin/env python3

from setuptools import setup


def get_version(fname='latexmake.py'):
    with open(fname) as f:
        for line in f:
            if line.startswith('__version__'):
                return eval(line.split('=')[-1])


def get_long_description():
    with open('README.rst') as f:
        return f.read()


setup(
      name='latexmake',
      version=get_version(),
      description=('Latexmake completely automates the process of '
                   'generating a LaTeX document.'),
      long_description=get_long_description(),
      author='Jan Kanis',
      author_email='jan.code@jankanis.nl',
      url='http://bitbucket.org/JanKanis/latexmake/',
      license='GPLv3+',
      platforms='any',
      classifiers=['Development Status :: 4 - Beta',
                   'Intended Audience :: End Users/Desktop',
                   'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Programming Language :: Python :: 3',
                   'Topic :: Printing',
                   'Topic :: Text Processing :: Markup :: LaTeX'],

      py_modules=['latexmake'],
      entry_points={'console_scripts': ['latexmake = latexmake:main']},
      )
