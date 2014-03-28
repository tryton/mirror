#!/usr/bin/env python
import setuptools

setuptools.setup(
    name='tryton_mirror',
    version='0.1',
    description='Tryton hg to git mirror',
    long_description=open('README.rst').read(),
    author='Sharoon Thomas (Openlabs)',
    author_email='sharoon.thomas@openlabs.co.in',
    url='http://github.com/tryton/mirror',
    packages=[
        'tryton_mirror',
    ],
    install_requires=[
        'mercurial', 'hg-git', 'envoy'
    ],
    scripts=['scripts/tryton_mirror', 'scripts/tryton_mirror_sync'],
    license='BSD License',
    zip_safe=False,
    keywords='tryton hg git mirror',
)
