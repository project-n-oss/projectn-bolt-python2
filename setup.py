#!/usr/bin/env python
import setuptools
from setuptools import setup

requires = ['boto3', 'botocore']
python_requires = '>=3'

setup(
    name='bolt-python-sdk',
    packages=setuptools.find_packages(),
    version='1.0.0',
    description='Bolt Python SDK',
    long_description=open('README.md').read(),
    author='Project N',
    install_requires=requires,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=python_requires,
    url="https://gitlab.com/projectn-oss/projectn-bolt-python",
)