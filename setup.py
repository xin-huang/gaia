# GNU General Public License v3.0
# Copyright 2024 Xin Huang
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, please see
#
#    https://www.gnu.org/licenses/gpl-3.0.en.html


import os.path
from setuptools import setup, find_packages

# The directory containing this file
HERE = os.path.abspath(os.path.dirname(__file__))

# The text of the README file
with open(os.path.join(HERE, "README.md")) as fid:
    README = fid.read()

# This call to setup() does all the work
setup(
    name="gaia",
    python_requires='>=3.9',
    version="1.0.0",
    description="A Python Package for Genomic Analysis of Introgressed Alleles with Machine Learning",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/xin-huang/gaia",
    author="Xin Huang, Josef Hackl",
    author_email="xinhuang.res@gmail.com",
    license="GPLv3",
    classifiers=[
        "License :: OSI Approved :: GNU General Public License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
    ],
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "demes",
        "msprime",
        "numpy",
        "pandas",
        "scikit-allel",
        "scikit-learn",
        "scipy",
    ],
    entry_points={"console_scripts": ["gaia=gaia.__main__:main"]},
)
