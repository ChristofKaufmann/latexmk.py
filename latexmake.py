#!/usr/bin/env python3
# coding: utf-8

'''
    latexmake
    ~~~~~~~~~

    Python module for latexmk.py which completely automates
    the process of generating a LaTeX document.

    :copyright: (c) 2012 by Marc Schlaich
    :license: MIT, see LICENSE for more details.
'''

from __future__ import with_statement

from io import open
from collections import defaultdict
from itertools import chain, takewhile
from subprocess import Popen, call
from textwrap import dedent
from hashlib import sha256

import argparse
import filecmp
import fnmatch
import logging
import os
import re
import shutil
import sys
import time
try:
    import notify2
except ImportError:
    notify2 = None

__author__ = 'Marc Schlaich'
__version__ = '0.4dev'
__license__ = 'MIT'


BIB_PATTERN = re.compile(r'\\bibdata\{(.*)\}')
CITE_PATTERN = re.compile(r'\\citation\{(.*)\}')
BIBCITE_PATTERN = re.compile(r'\\bibcite\{(.*)\}\{(.*)\}')
BIBENTRY_PATTERN = re.compile(r'@.*\{(.*),\s')
ERROR_PATTTERN = re.compile(r'(?:^! (.*\nl\..*)$)|(?:^! (.*)$)|'
                            '(No pages of output.)', re.M)
LATEX_RERUN_PATTERNS = [re.compile(pattr) for pattr in
                        [r'LaTeX Warning: Reference .* undefined',
                         r'LaTeX Warning: There were undefined references\.',
                         r'LaTeX Warning: Label\(s\) may have changed\.',
                         r'No file .*(\.toc|\.lof)\.']]
TEXLIPSE_MAIN_PATTERN = re.compile(r'^mainTexFile=(.*)(?:\.tex)$', re.M)

LATEX_FLAGS = ['-interaction=nonstopmode', '-shell-escape', '--synctex=1']
MAX_RUNS = 4
NO_LATEX_ERROR = (
    'Could not run command "%s". '
    'Is your latex distribution under your PATH?'
)

log = logging.getLogger(__name__)
log.addHandler(logging.StreamHandler()) 

class LatexMaker:
    '''
    Main class for generation process.
    '''
    def __init__(self, project_name, opt, log=None):
        self.opt = opt
        self.log = log
        if self.log == None: 
            self.log = globals()['log']

        if project_name == '.texlipse':
            self.project_name = self._parse_texlipse_config()
        else:
            self.project_name = project_name

        if self.project_name.endswith('.tex'):
            self.project_name = self.project_name[:-4]

        if self.opt.command:
            self.latex_cmd = self.opt.command
        elif self.opt.pdf:
            self.latex_cmd = 'pdflatex'
        else:
            self.latex_cmd = 'latex'

        self.out = ''
        self.glossaries = dict()
        self.latex_run_counter = 0
        self.bib_file = ''

    def _parse_texlipse_config(self):
        '''
        Read the project name from the texlipse
        config file ".texlipse".
        '''
        # If Eclipse's workspace refresh, the
        # ".texlipse"-File will be newly created,
        # so try again after short sleep if
        # the file is still missing.
        if not os.path.isfile('.texlipse'):
            time.sleep(0.1)
            if not os.path.isfile('.texlipse'):
                self._fatal_error('! Fatal error: File .texlipse is missing.')

        with open('.texlipse') as fobj:
            content = fobj.read()
        match = TEXLIPSE_MAIN_PATTERN.search(content)
        if match:
            project_name = match.groups()[0]
            self.log.info('Found inputfile in ".texlipse": %s.tex'
                          % project_name)
            return project_name
        else:
            self._fatal_error('! Fatal error: Parsing .texlipse failed.')

    def _read_latex_files(self):
        '''
        Check if some latex output files exist
        before first latex run, process them and return
        the generated data.

            - Parsing *.aux for citations counter and
              existing glossaries.
            - Getting content of files to detect changes.
                - *.toc file
                - all available glossaries files
        '''
        if os.path.isfile('%s.aux' % self.project_name):
            cite_counter = self.generate_citation_counter()
            self.read_glossaries()
        else:
            cite_counter = {'%s.aux' % self.project_name:
                            defaultdict(int)}

        fname = '%s.toc' % self.project_name
        if os.path.isfile(fname):
            with open(fname, 'rb') as fobj:
                toc_sha = hashlib.sha265(fobj.read()).digest()
        else:
            toc_sha = ''

        gloss_files = dict()
        for gloss in self.glossaries:
            ext = self.glossaries[gloss][1]
            filename = '%s.%s' % (self.project_name, ext)
            if os.path.isfile(filename):
                with open(filename) as fobj:
                    gloss_files[gloss] = fobj.read()

        return cite_counter, toc_sha, gloss_files

    def _is_toc_changed(self, toc_sha):
        '''
        Test if the *.toc file has changed during
        the first latex run.
        '''
        fname = '%s.toc' % self.project_name
        if os.path.isfile(fname):
            with open(fname, 'rb') as fobj:
                if hashlib.sha256(fobj.read()).digest() != toc_sha:
                    return True

    def _need_bib_run(self, old_cite_counter):
        '''
        Determine if you need to run "bibtex".
        1. Check if *.bib exists.
        2. Check latex output for hints.
        3. Test if the numbers of citations changed
           during first latex run.
        4. Examine *.bib for changes.
        '''
        with open('%s.aux' % self.project_name) as fobj:
            match = BIB_PATTERN.search(fobj.read())
            if not match:
                return False
            else:
                self.bib_file = match.group(1)

        if not os.path.isfile('%s.bib' % self.bib_file):
            self.log.warning('Could not find *.bib file.')
            return False

        if (re.search('No file %s.bbl.' % self.project_name, self.out) or
            re.search('LaTeX Warning: Citation .* undefined', self.out)):
            return True

        if old_cite_counter != self.generate_citation_counter():
            return True

        if os.path.isfile('%s.bib.old' % self.bib_file):
            new = '%s.bib' % self.bib_file
            old = '%s.bib.old' % self.bib_file
            if not filecmp.cmp(new, old):
                return True

    def _fatal_error(self, msg):
        '''
        Log the error to the logger and raise a LatexMkError
        '''
        self.log.error(msg)
        raise LatexMkError(msg)

    def read_glossaries(self):
        '''
        Read all existing glossaries in the main aux-file.
        '''
        filename = '%s.aux' % self.project_name
        with open(filename) as fobj:
            main_aux = fobj.read()

        pattern = r'\\@newglossary\{(.*)\}\{.*\}\{(.*)\}\{(.*)\}'
        for match in re.finditer(pattern, main_aux):
            name, ext_i, ext_o = match.groups()
            self.glossaries[name] = (ext_i, ext_o)

    def check_errors(self):
        '''
        Check if errors occured during a latex run by
        scanning the output.
        '''
        errors = ERROR_PATTTERN.findall(self.out)
        # "errors" is a list of tuples
        if errors:
            self.log.error('! Errors occurred:')

            error = '\n'.join(
                [error.replace('\r', '').strip() for error
                in chain(*errors) if error.strip()]
            )
            
            self.log.error(error)

            self.log.error('! See "%s.log" for details.' % self.project_name)

            if self.opt.exit_on_error:
                raise LatexMkError('\n'.join((error, 
                    'See "{}.log" for details.'.format(self.project_name))
                ))

    def generate_citation_counter(self):
        '''
        Generate dictionary with the number of citations in all
        included files. If this changes after the first latex run,
        you have to run "bibtex".
        '''
        cite_counter = dict()
        filename = '%s.aux' % self.project_name
        with open(filename) as fobj:
            main_aux = fobj.read()
        cite_counter[filename] = _count_citations(filename)

        for match in re.finditer(r'\\@input\{(.*\.aux)\}', main_aux):
            filename = match.groups()[0]
            try:
                counter = _count_citations(filename)
            except IOError:
                pass
            else:
                cite_counter[filename] = counter

        return cite_counter

    def latex_run(self):
        '''
        Start latex run.
        '''
        self.log.info('Running %s...' % self.latex_cmd)
        cmd = [self.latex_cmd]
        cmd.extend(LATEX_FLAGS)
        cmd.extend(['-jobname', self.project_name, '%s.tex' % self.project_name])

        try:
            with open(os.devnull, 'w') as null:
                Popen(cmd, stdout=null, stderr=null).wait()
        except OSError:
            self._fatal_error(NO_LATEX_ERROR % self.latex_cmd)
        self.latex_run_counter += 1

        with open('%s.log' % self.project_name) as fobj:
            self.out = fobj.read()
        self.check_errors()

    def bibtex_run(self):
        '''
        Start bibtex run.
        '''
        self.log.info('Running bibtex...')
        try:
            with open(os.devnull, 'w') as null:
                Popen(['bibtex', self.project_name], stdout=null).wait()
        except OSError:
            self._fatal_error(NO_LATEX_ERROR % 'bibtex')

        shutil.copy('%s.bib' % self.bib_file,
                    '%s.bib.old' % self.bib_file)

    def makeindex_runs(self, gloss_files):
        '''
        Check for each glossary if it has to be regenerated
        with "makeindex".

        @return: True if "makeindex" was called.
        '''
        gloss_changed = False
        for gloss in self.glossaries:
            make_gloss = False
            ext_i, ext_o = self.glossaries[gloss]
            fname_in = '%s.%s' % (self.project_name, ext_i)
            fname_out = '%s.%s' % (self.project_name, ext_o)
            if re.search('No file %s.' % fname_in, self.out):
                make_gloss = True
            if not os.path.isfile(fname_out):
                make_gloss = True
            else:
                with open(fname_out) as fobj:
                    try:
                        if gloss_files[gloss] != fobj.read():
                            make_gloss = True
                    except KeyError:
                        make_gloss = True

            if make_gloss:
                self.log.info('Running makeindex (%s)...' % gloss)
                try:
                    cmd = ['makeindex', '-q', '-s',
                           '%s.ist' % self.project_name,
                           '-o', fname_in, fname_out]
                    with open(os.devnull, 'w') as null:
                        Popen(cmd, stdout=null).wait()
                except OSError:
                    self._fatal_error(NO_LATEX_ERROR % 'makeindex')
                gloss_changed = True

        return gloss_changed

    def open_preview(self):
        '''
        Try to open a preview of the generated document.
        '''
        self.log.info('Opening preview...')
        if self.opt.pdf:
            ext = 'pdf'
        else:
            ext = 'dvi'
        filename = '%s.%s' % (self.project_name, ext)
        if sys.platform == 'win32':
            try:
                os.startfile(filename)
            except OSError:
                self.log.error(
                    'Preview-Error: Extension .%s is not linked to a '
                    'specific application!' % ext
                )
        elif sys.platform == 'darwin':
            call(['open', filename])
        else:
        # Works on most Linuxes
            try:
                call(['xdg-open', filename])
            except OSError as e:
                self.log.error('Preview-Error: opening previewer failed with '
                    'the following message:\n'
                    + str(e))

    def need_latex_rerun(self):
        '''
        Test for all rerun patterns if they match the output.
        '''
        for pattern in LATEX_RERUN_PATTERNS:
            if pattern.search(self.out):
                return True
        return False

    def run(self):
        '''Run the LaTeX compilation.'''
        # store files
        self.old_dir = []
        if self.opt.clean:
            self.old_dir = os.listdir('.')

        cite_counter, toc_sha, gloss_files = self._read_latex_files()

        self.latex_run()
        self.read_glossaries()

        gloss_changed = self.makeindex_runs(gloss_files)
        if gloss_changed or self._is_toc_changed(toc_sha):
            self.latex_run()

        if self._need_bib_run(cite_counter):
            self.bibtex_run()
            self.latex_run()

        while (self.latex_run_counter < MAX_RUNS):
            if not self.need_latex_rerun():
                break
            self.latex_run()

        if self.opt.check_cite:
            cites = set()
            with open('%s.aux' % self.project_name) as fobj:
                aux_content = fobj.read()

            for match in BIBCITE_PATTERN.finditer(aux_content):
                name = match.groups()[0]
                cites.add(name)

            with open('%s.bib' % self.bib_file) as fobj:
                bib_content = fobj.read()
            for match in BIBENTRY_PATTERN.finditer(bib_content):
                name = match.groups()[0]
                if name not in cites:
                    self.log.info('Bib entry not cited: "%s"' % name)

        if self.opt.clean:
            ending = '.dvi'
            if self.opt.pdf:
                ending = '.pdf'

            for fname in os.listdir('.'):
                if not (fname in self.old_dir or fname.endswith(ending)):
                    try:
                        os.remove(fname)
                    except IOError:
                        pass

        if self.opt.preview:
            self.open_preview()

        msg = "'{}.tex' compiled".format(self.project_name)
        self.log.info(msg)
        if self.opt.notify:
            notify(msg)


class LatexMkError (Exception):
    pass


class NotifyHandler (logging.Handler):
    '''
    A Logging handler that sends messages to the Gnome notification system
    using the 'notify-send' command. Default level is ERROR. This handler 
    guards against infinite recursion of errors caused by notification failure.
    '''
    def __init__(self, level=logging.ERROR, *args):
        logging.Handler.__init__(self, *args, level=level)
        #self.addFilter(notifyfilter)

    def emit(self, record):
        notify('LatexMk error:', record.getMessage())

# def notifyfilter(record):
#     if isinstance(record.args, dict) and \
#             record.args.get(__name__+'-recursing') == 'recursing':
#         return False
#     return True


def notify(sum, msg=None):
    if not msg is None:
        notify2.Notification(sum, msg).show()
    else:
        notify2.Notification(sum).show()

def _count_citations(aux_file):
    '''
    Counts the citations in an aux-file.

    @return: defaultdict(int) - {citation_name: number, ...}
    '''
    counter = defaultdict(int)
    with open(aux_file) as fobj:
        content = fobj.read()

    for match in CITE_PATTERN.finditer(content):
        name = match.groups()[0]
        counter[name] += 1

    return counter


def main():
    '''
    Set up "argparse" and pass the options to
    a new instance of L{LatexMaker}.
    '''

    # Read description from doc. Add a space because argparse removes empty 
    # trailing lines from the description. 
    doc_text = dedent(__doc__.split('\n#', 1)[0]) + ' '

    parser = argparse.ArgumentParser(description=doc_text, formatter_class=
                              argparse.RawDescriptionHelpFormatter)
    parser.add_argument('filename', default=None, nargs='?', 
                      help='''input filename. If omitted the current directory
                            will be searched for a single *.tex file. Specify 
                            ".texlipse" to find the .tex file from a *.texlipse
                            project file.''')
    parser.add_argument('-c', '--clean',
                      action='store_true', dest='clean', default=False,
                      help='clean all temporary files after converting')
    parser.add_argument('-q', '--quiet',
                      action='count', dest='quiet', default=0, 
                      help='don\'t print status messages to stdout. specify '
                          'twice not to show error messages either.')
    parser.add_argument('-d', '--debug', 
                      action='store_const', dest='quiet', const=-1, default=0, 
                      help='show debugging information')
    parser.add_argument('-n', '--no-exit',
                      action='store_false', dest='exit_on_error', default=True,
                      help='don\'t exit if error occurs')
    parser.add_argument('-N', '--notify', 
                      action='store_true', dest='notify', default=False, 
                      help='''Notify through the desktop environment if a 
                          rebuild is finished and if errors occured. Currently 
                          only available on Gnome.''')
    parser.add_argument('-p', '--preview',
                      action='store_true', dest='preview', default=False,
                      help='try to open preview of generated document')
    parser.add_argument('--dvi', action='store_false', dest='pdf',
                      default=True, help='use "latex" instead of pdflatex')
    parser.add_argument('-t', '--tex-command', dest='command', 
                      help='the latex compiler command to use')
    parser.add_argument('--check-cite', action='store_true', dest='check_cite',
                      default=False,
                      help='check bibtex file for uncited entries')
    parser.add_argument('--version', action='version', 
                      version='%(prog)s {}'.format(__version__))

    args, rest = parser.parse_known_args()
    if rest:
        parser.error(
            'unrecognized arguments: {}. Specify at most one filename'
                .format(' '.join(('"{}"'.format(r) for r in rest))))
    if args.filename == None:
        tex_files = fnmatch.filter(os.listdir(os.getcwd()), '*.tex')
        if len(tex_files) == 1:
            args.filename = tex_files[0]
        elif len(tex_files) == 0:
            parser.error('could not find one *.tex file in current directory')
        else:
            parser.error('multiple *.tex files in current directory, specify only one')
  
    if args.notify:
        if notify2 is None:
            parser.error("Unable to use desktop notification ('-N', '--notify'). "
                "Could not load package 'notify2'.")
        else:
            notify2.init('LatexMk')
            log.addHandler(NotifyHandler())

    args.verbosity = \
        {-1: logging.DEBUG, 0: logging.INFO, 
         1: logging.ERROR, 2: logging.FATAL}[min(args.quiet, 2)]
    log.setLevel(args.verbosity)

    log.debug('arguments: '+str(args))
    
    try:
        LatexMaker(args.filename, args, log=log).run()
    except LatexMkError as e:
        # The exceptions message is already logged
        log.error('! Exiting...')
        sys.exit(1)

if __name__ == '__main__':
    main()
