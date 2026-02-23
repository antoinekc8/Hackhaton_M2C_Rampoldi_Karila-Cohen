from setuptools import setup, Extension
from Cython.Build import cythonize

# This tells Cython to compile checker.py into a binary
ext_modules = [
    Extension(
        "checker",
        ["checker.py"],
        # This part is optional but helps with some Mac-specific linking
        extra_compile_args=['-O3'],
    )
]

setup(
    name='CheckerModule',
    ext_modules=cythonize(ext_modules, language_level="3"),
)