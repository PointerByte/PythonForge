"""Maps the flat src/ tree onto the `pythonforge` package name.

pyproject.toml holds all metadata; this file exists only because the
directory-to-package mapping (src/ -> pythonforge/) needs subpackages
discovered dynamically, which the declarative config cannot express.
"""

from setuptools import find_packages, setup

setup(
    packages=["pythonforge", *(f"pythonforge.{pkg}" for pkg in find_packages("src"))],
    package_dir={"pythonforge": "src"},
)
