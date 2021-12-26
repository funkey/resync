from setuptools import setup

setup(
        name='resync',
        version='0.1',
        url='https://github.com/funkey/resync',
        author='Jan Funke',
        author_email='funkej@janelia.hhmi.org',
        license='MIT',
        packages=[
            'resync'
        ],
        scripts=[
            'scripts/refs'
        ]
)
