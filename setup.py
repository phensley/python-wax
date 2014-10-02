
from os.path import abspath, dirname, exists, join
from setuptools import setup

from wax import __version__

reader = lambda n: open(join(dirname(abspath(__file__)), n)).read()

opts = dict(
    name = 'python-wax',
    version = __version__,
    description = 'A hierarchical configuration format and context object for Python',
    author = 'Patrick Hensley',
    author_email = 'spaceboy@indirect.com',
    keywords = ['config', 'configuration', 'json', 'ini'],
    url = 'http://github.com/phensley/python-wax',
    packages = ['wax'],
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)

if exists('README.txt'):
    opts['long_description'] = reader('README.txt')

setup(**opts)

