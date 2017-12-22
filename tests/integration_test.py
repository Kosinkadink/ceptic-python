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


def test_pinging():
	client = ExampleClient(location=test_pinging.test_clientlocation,start_terminal=False)
	server = ExampleServer(location=test_pinging.test_serverlocation,start_terminal=False,block_on_start=False)
	server.start()
	# attempt to ping
	attempt = client.ping_terminal_command("localhost:9999")
	print(attempt)
	# check if response is valid
	assert isinstance(attempt,dict)
	assert attempt["status"] == 200
	assert attempt["msg"] == "pong"


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
	try:
		copytree(function.archive_client_certification_dir,function.actual_certification_clientdir)
	except WindowsError: # already exists
		pass
	try:
		copytree(function.archive_server_certification_dir,function.actual_certification_serverdir)
	except WindowsError: # already exists
		pass

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

if __name__ == "__main__":
	testfiles_servername = "testfilesserver"
	testfiles_clientname = "testfilesclient"
	test_dir = os.path.join(os.path.realpath(
		os.path.join(os.getcwd(), os.path.dirname(__file__))))
	test_clientlocation = os.path.join(test_dir,testfiles_clientname)
	test_serverlocation = os.path.join(test_dir,testfiles_servername)
	resource_clientdir = os.path.join(test_clientlocation,"resources")
	resource_serverdir = os.path.join(test_serverlocation,"resources")
	actual_certification_clientdir = os.path.join(resource_clientdir, "certification")
	actual_certification_serverdir = os.path.join(resource_serverdir, "certification")
	archive_client_certification_dir = os.path.join(test_dir,"client_certs/certification")
	archive_server_certification_dir = os.path.join(test_dir,"server_certs/certification")
	try:
		copytree(archive_server_certification_dir,actual_certification_serverdir)
	except WindowsError:
		pass
	try:
		copytree(archive_client_certification_dir,actual_certification_clientdir)
	except WindowsError:
		pass
	client = ExampleClient(location=test_clientlocation,start_terminal=False)
	server = ExampleServer(location=test_serverlocation,start_terminal=False,block_on_start=False)
	server.start()
	sleep(2)
	attempt = client.ping_terminal_command("localhost:9999")
	print(attempt)
	server.exit()
	sleep(1)
