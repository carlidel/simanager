from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="simanager",
    version="0.0.4",
    author="Carlo Emilio Montanari",
    author_email="carlo.emilio.montanari@cern.ch",
    description="A Python package for managing simulations locally, on HTCondor and on Slurm, with some specific elements that are good in a CERNy environment.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/carlidel/simanager",
    packages=find_packages(),
    install_requires=["numpy", "pyyaml"],
    include_package_data=True,
    # Add command line tools
    entry_points={
        "console_scripts": [
            "simanager=simanager.cli_tools:main",
        ],
    },
    # MIT license
    license="MIT",
)
