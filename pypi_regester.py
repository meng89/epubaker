#!/usr/bin/env python3
import os

#os.system('pandoc --from org --to rst -s README.org -o README.rst')
os.system('python setup.py register')
#os.remove('README.rst')