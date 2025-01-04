from setuptools import setup, find_packages
import os

this_directory = os.path.abspath(os.path.dirname(__file__))
readme_path = os.path.join(this_directory, "readme_pypi.md")

with open(readme_path, 'r') as f:
    long_description = f.read()

setup(
    name='energy_tariff_scheduler',
    version='0.0.6', # TODO: link this to a file which is shared and bumped on twine run
    author='Craig White',
    author_email='dev.craigw@gmail.com',
    description='Schedule actions based on energy tariffs',
    packages=find_packages(exclude=["__tests__", ".env"], include=["energy_tariff_scheduler"]),
    install_requires=[
        "pydantic==2.10.4",
        "requests==2.32.3",
        "python-dateutil==2.9.0.post0",
        "apscheduler==3.11.0",
        "tenacity==9.0.0"
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    license='MIT',
    python_requires='>=3.10',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/craigwh10/energy-tariff-scheduler"   
)