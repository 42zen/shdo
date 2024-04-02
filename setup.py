from setuptools import setup

setup(
    name='shdo',
    version='0.0.7',
    packages=['shdo'],
    package_dir={'shdo': '.'},
    py_modules=['shdo'],
    entry_points={
        'console_scripts': [
            'shdo = shdo:main',
            'shdo-pair = shdo:main',
        ]
    },
    author='Zen',
    description='A tool to escalate privileges in Android',
    long_description='Shdo is a tool that helps you run elevated commands in Android (similar to sudo) without requiring root access. It utilizes debug privileges instead of root privileges.',
    url='https://github.com/42zen/shdo',
)