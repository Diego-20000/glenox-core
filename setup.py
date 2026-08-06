from setuptools import find_packages, setup

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="glenox-core",
    version="0.1.0",
    description="Multi-provider LLM completion router with automatic fallback and credit-based cost governance.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=("tests", "tests.*")),
    install_requires=[
        "pydantic==2.9.2",
    ],
    extras_require={
        "dev": ["pytest==8.3.3"],
    },
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
