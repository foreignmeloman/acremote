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
    version='0.1',
    description='<description_placeholder>',  # actual "Summary" field in egg-info
    long_description='<long_description_placeholder>',
    url='https://github.com/foreignmeloman',
    author='foreignmeloman',
    author_email='foreignmeloman@gmail.com',
    license='MIT',
    ext_modules=[module_gpirblast],
    # py_modules=['acremote'],
    packages=find_packages(exclude=['tests', 'config_templates']),
    extras_require={
        ':python_version == "3.5"': [
            'yarl<=1.3.0',
            'aiohttp<=3.6.1',
            'telepot==12.7',
        ],
        ':python_version > "3.5"': [
            'telepot',
        ],
    },
)
