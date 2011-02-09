from mifcholib import version
from distutils.core import setup
import glob

setup(
	name=version.APP_NAME,
	version=version.APP_VERSION,
	description='MIddleware For Connection Handling and Orchestration',
	author='Simon A. F. Lund',
	author_email='mifcho@safl.dk',
	url='http://code.google.com/p/mifcho/',
	license='GNU GPL v3',
	scripts=['mifcho'],
	packages=['mifcholib']
)
