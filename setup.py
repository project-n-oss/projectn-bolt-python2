#!/usr/bin/env python
import setuptools
from setuptools import setup
import io
import sys

requires = ['boto3', 'botocore']
python_requires = '>=2.7'

with io.open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

if sys.version_info[0] == 2:
    # python2 sdk version
    version = '1.0.0'
else:
    # python3 SDK version
    version = '2.1.8'

setup(
    name='bolt-sdk',
    packages=setuptools.find_packages(),
    version=version,
    description='Bolt Python SDK',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Project N',
    install_requires=requires,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Software Development :: Libraries",
    ],
    python_requires=python_requires,
    url="https://gitlab.com/projectn-oss/projectn-bolt-python",
)
