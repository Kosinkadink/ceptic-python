from distutils.core import setup

ceptic_version = '1.0.0'

setup(
    name='ceptic',
    version=ceptic_version,
    packages=['ceptic'],
    url='https://github.com/kosinkadink/ceptic',
    download_url = 'https://github.com/kosinkadink/ceptic/archive/{}.tar.gz'.format(ceptic_version),
    license='MIT',
    author='Jedrzej Kosinski',
    author_email='kosinkadink1@gmail.com',
    description=''
)
