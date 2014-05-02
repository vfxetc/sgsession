from setuptools import setup, find_packages

setup(
    name='sgsession',
    version='0.1-dev',
    description='Shotgun ORM/Session.',
    url='http://github.com/westernx/sgsession',
    
    packages=find_packages(exclude=['build*', 'tests*']),
    
    author='Mike Boers',
    author_email='sgsession@mikeboers.com',
    license='BSD-3',
    
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    
)
