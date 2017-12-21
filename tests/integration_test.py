from testingfixtures import add_surrounding_dir_to_path
# add surrounding dir to path to enable importing
add_surrounding_dir_to_path()

from client_test import ExampleClient
from server_test import ExampleServer
from ceptic.common import normalize_path
from shutil import rmtree, copytree
from time import sleep
import sys
import os




# set up for each function
def setup_function(function):
	testfiles_clientname = "testfilesclient"
	testfiles_servername = "testfilesserver"
	function.test_dir = os.path.join(os.path.realpath(
		os.path.join(os.getcwd(), os.path.dirname(__file__))))
	function.test_clientlocation = os.path.join(function.test_dir,testfiles_clientname)
	function.test_serverlocation = os.path.join(function.test_dir,testfiles_servername)
	resource_clientdir = os.path.join(function.test_clientlocation,"resources")
	resource_serverdir = os.path.join(function.test_serverlocation,"resources")
	function.actual_certification_clientdir = os.path.join(resource_clientdir, "certification")
	function.actual_certification_serverdir = os.path.join(resource_serverdir, "certification")
	function.archive_client_certification_dir = os.path.join(function.test_dir,"client_certs/certification")
	function.archive_server_certification_dir = os.path.join(function.test_dir,"server_certs/certification")
	copytree(function.archive_certification_dir,function.actual_certification_dir)

def teardown_function(function):
	# remove everything BUT the resources/certification directory
	rmtree(function.test_clientlocation)
	rmtree(function.test_serverlocation)

# done setting up objects for each module


# setup objects for this module
def setup_module(module):
	pass

def teardown_module(module):
	pass
