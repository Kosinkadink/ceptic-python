from testingfixtures import add_surrounding_dir_to_path
# add surrounding dir to path to enable importing
add_surrounding_dir_to_path()

from ceptic.client import CepticClientTemplate, main
from ceptic.common import normalize_path
from shutil import rmtree, copytree
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
	# list of directories that should exist
	directories = [
		"resources",
		"resources/protocols",
		"resources/cache",
		"resources/programparts",
		"resources/uploads",
		"resources/downloads",
		"resources/networkpass",
		"resources/certification"
	]
	# list of files that should exist
	files = [
		"resources/certification/techtem_cert_client.pem",
		"resources/certification/techtem_cert_server.pem",
		"resources/certification/techtem_key_client.pem",
		"resources/certification/techtem_key_server.pem"
	]
	# check if directories exist
	for directory in directories:
		fullpath = os.path.join(test_location,directory)
		print fullpath
		assert os.path.isdir(fullpath)
	# check if files exist
	for file in files:
		fullpath = os.path.join(test_location,file)
		print fullpath
		assert os.path.isfile(fullpath)

# END TESTS




# setup objects for this module
def setup_module(module):
	testfiles_name = "testfiles"
	module.test_dir = os.path.join(os.path.realpath(
		os.path.join(os.getcwd(), os.path.dirname(__file__))))
	module.test_location = os.path.join(module.test_dir,testfiles_name)
	resource_dir = os.path.join(module.test_location,"resources")
	actual_certification_dir = os.path.join(resource_dir, "certification")
	archive_certification_dir = os.path.join(module.test_dir,"certification")
	copytree(archive_certification_dir,actual_certification_dir)

def teardown_module(module):
	# remove everything BUT the resources/certification directory
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
