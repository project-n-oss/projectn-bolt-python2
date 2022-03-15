#!/usr/bin/env python
import setuptools
from setuptools import setup

requires = ['boto3', 'botocore']
python_requires = '>=3'


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='bolt-sdk',
    packages=setuptools.find_packages(),
    version='2.0.3',
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