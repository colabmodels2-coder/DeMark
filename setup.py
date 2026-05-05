from setuptools import setup, find_packages

setup(
    name="demark-dashboard",
    version="1.0.0",
    description="Interactive DeMark TD Sequential market dashboard based on Jason Perl's methodology",
    author="Sean",
    packages=find_packages(),
    install_requires=[
        "streamlit>=1.44",
        "pandas>=2.2",
        "numpy>=1.26",
        "plotly>=5.20",
        "yfinance>=0.2.54",
        "python-dateutil>=2.9",
    ],
    python_requires=">=3.10",
)
