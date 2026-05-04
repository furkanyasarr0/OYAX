from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules = cythonize(["license_system.py", "app.py"], language_level=3)
)
