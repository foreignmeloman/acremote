import os
from setuptools import setup, Extension, find_packages

here = os.path.abspath(os.path.dirname(__file__))

module_gpirblast = Extension(
    'gpirblast',
    sources=[os.path.join(here, 'gpirblast', 'gpirblast.c')],
    include_dirs=[
        os.path.join(here, 'gpirblast'),
    ],
    libraries=['pigpio'],
)


setup(  # TODO fill the form
    name='acremote',
    version='0.1.0',
    description='<description_placeholder>',  # actual "Summary" field in egg-info
    long_description='<long_description_placeholder>',
    url='https://github.com/foreignmeloman',
    author='foreignmeloman',
    author_email='foreignmeloman@gmail.com',
    license='MIT',
    ext_modules=[module_gpirblast],
    packages=find_packages(exclude=['tests', 'config_templates']),
    python_requires='>=3.7',
    install_requires=[
        'telepot',
    ],
)
