from setuptools import find_packages, setup

version = '1.1.4'

setup(
    name='sdh.table',
    version=version,
    url='https://bitbucket.org/sdh-llc/sdh-table/',
    author='Software Development Hub LLC',
    author_email='dev-tools@sdh.com.ua',
    description='Table rendering engine',
    license='BSD',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    namespace_packages=['sdh'],
    eager_resources=['sdh'],
    include_package_data=True,
    entry_points={},
    install_requires=['Django>=1.8', ],
    zip_safe=False,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
