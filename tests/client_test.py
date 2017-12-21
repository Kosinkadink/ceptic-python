from testingfixtures import add_surrounding_dir_to_path
# add surrounding dir to path to enable importing
add_surrounding_dir_to_path()

from ceptic.client import CepticClientTemplate, main
from ceptic.common import normalize_path
from shutil import rmtree
from time import sleep
import sys
import os


class ExampleClient(CepticClientTemplate):

	def __init__(self, location, start_terminal):
		name = "test"
		version = "3.0.0"
		CepticClientTemplate.__init__(self, location, start_terminal, name=name, version=version)

	def add_terminal_commands(self):
		self.terminalManager.add_command("ping", lambda data: self.ping_terminal_command(data[1]))


# TESTS:

def test_creation():

	client = ExampleClient(location=test_location,start_terminal=False)


# END TESTS




# setup objects for this module
def setup_module(module):
	testfiles_name = "testfiles"
	module.test_dir = os.path.join(os.path.realpath(
		os.path.join(os.getcwd(), os.path.dirname(__file__))))
	module.test_location = os.path.join(module.test_dir,testfiles_name)
	# create directory
	os.mkdir(module.test_location)

def teardown_module(module):
	# remove test_location
	rmtree(module.test_location)

# done setting up objects for this module

# set up for each function
def setup_function(function):
	pass

def teardown_function(function):
	pass
# done setting up objects for each function




if __name__ == "__main__":
	__location__ = normalize_path(os.path.realpath(
		os.path.join(os.getcwd(), os.path.dirname(__file__))))  # directory from which this script is ran
	main(sys.argv[1:], TestClient, __location__, start_terminal=True)
