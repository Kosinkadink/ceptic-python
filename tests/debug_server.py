from testingfixtures import add_surrounding_dir_to_path
# add surrounding dir to path to enable importing
add_surrounding_dir_to_path()

from client_test import ExampleClient
from server_test import ExampleServer
from ceptic.common import normalize_path
from shutil import rmtree, copytree
from time import sleep, time
import pytest
import sys
import os

if os.name != "nt":
	WindowsError = OSError


def setup_server():
	testfiles_servername = "testfilesserver"
	test_dir = os.path.join(os.path.realpath(
		os.path.join(os.getcwd(), os.path.dirname(__file__))))
	test_serverlocation = os.path.join(test_dir,testfiles_servername)
	resource_serverdir = os.path.join(test_serverlocation,"resources")
	actual_certification_serverdir = os.path.join(resource_serverdir, "certification")
	archive_server_certification_dir = os.path.join(test_dir,"server_certs/certification")
	try:
		copytree(archive_server_certification_dir,actual_certification_serverdir)
	except WindowsError:
		pass
	return test_serverlocation


if __name__ == "__main__":
	location = setup_server()
	server = ExampleServer(location=location,start_terminal=True,block_on_start=True)
	server.start()
