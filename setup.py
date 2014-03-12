from setuptools import setup, find_packages

from helga_karma import __version__ as version


requirements = []
with open('requirements.txt', 'r') as in_:
    requirements = in_.readlines()


setup(
    name='helga-karma',
    version=version,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: IRC',
        'Intended Audience :: Twisted Developers, IRC Bot Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: IRC Bots'
    ],
    author='Adam Coddington',
    author_email='me@adamcoddington.net',
    url='https://github.com/coddingtonbear/helga-karma',
    license='MIT',
    packages=find_packages(),
    entry_points={
        'helga_plugins': [
            'karma = helga_karma.plugin:KarmaPlugin',
        ]
    },
    install_requires=requirements,
    tests_require=[
        'nose',
    ]
)
