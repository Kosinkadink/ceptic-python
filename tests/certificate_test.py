from testingfixtures import add_surrounding_dir_to_path
# add surrounding dir to path to enable importing
add_surrounding_dir_to_path()

from client_test import ExampleClient
from server_test import ExampleServer
from ceptic.common import normalize_path
from shutil import rmtree, copytree
from time import sleep, time
from pytest import raises
import pytest
import sys
import os

def test_pinging_client_verify():
	client = ExampleClient(location=test_pinging_client_verify.test_clientlocation,start_terminal=False)
	test_pinging_client_verify.server.start()
	test_pinging_client_verify.server_noverify.start()
	# attempt to ping
	attempt = client.ping_terminal_command("localhost:9999")
	attempt_noverify = client.ping_terminal_command("localhost:9998")
	print(attempt)
	print(attempt_noverify)
	# check if response is valid

	# BOTH servers should respond properly
	assert isinstance(attempt,dict)
	assert attempt["status"] == 200
	assert attempt["msg"] == "pong"
	assert isinstance(attempt_noverify,dict)
	assert attempt_noverify["status"] == 200
	assert attempt_noverify["msg"] == "pong"

def test_pinging_client_no_verify():
	client = ExampleClient(location=test_pinging_client_verify.test_clientlocation,start_terminal=False,client_verify=False)
	test_pinging_client_no_verify.server.start()
	test_pinging_client_no_verify.server_noverify.start()
	# attempt to ping
	attempt = client.ping_terminal_command("localhost:9999")
	attempt_noverify = client.ping_terminal_command("localhost:9998")
	print(attempt)
	print(attempt_noverify)
	# check if response is valid

	# Verify should NOT PASS, NoVerify should PASS, 
	assert isinstance(attempt,dict)
	assert attempt["status"] != 200
	assert attempt["msg"] != "pong"
	assert isinstance(attempt_noverify,dict)
	assert attempt_noverify["status"] == 200
	assert attempt_noverify["msg"] == "pong"

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
	function.actual_uploads_clientdir = os.path.join(resource_clientdir, "uploads")
	function.actual_uploads_serverdir = os.path.join(resource_serverdir, "uploads")
	function.archive_uploads_clientdir = os.path.join(function.test_dir,"client_certs/uploads")
	function.archive_uploads_serverdir = os.path.join(function.test_dir,"server_certs/uploads")
	try:
		copytree(function.archive_client_certification_dir,function.actual_certification_clientdir)
	except OSError: # already exists
		pass
	try:
		copytree(function.archive_server_certification_dir,function.actual_certification_serverdir)
	except OSError: # already exists
		pass
	try:
		copytree(function.archive_uploads_clientdir,function.actual_uploads_clientdir)
	except OSError: # already exists
		pass
	try:
		copytree(function.archive_uploads_serverdir,function.actual_uploads_serverdir)
	except OSError: # already exists
		pass
	# setup server
	function.server = ExampleServer(location=function.test_serverlocation,start_terminal=False,block_on_start=False,client_verify=True)
	function.server_noverify = ExampleServer(location=function.test_serverlocation,start_terminal=False,server=9998,user=10998,block_on_start=False,client_verify=False)

def teardown_function(function):
	# remove everything
	rmtree(function.test_clientlocation)
	rmtree(function.test_serverlocation)
	# stop the server, if exists
	try:
		function.server.exit()
		function.server_noverify.exit()
		sleep(0.1)
	except Exception as e:
		print(str(e))

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
	except OSError:
		pass
	try:
		copytree(archive_client_certification_dir,actual_certification_clientdir)
	except OSError:
		pass
	client = ExampleClient(location=test_clientlocation,start_terminal=False)
	server = ExampleServer(location=test_serverlocation,start_terminal=False,block_on_start=False)
	server.start()
	frame_count = 20
	delay_time = 0
	start = time()
	attempt = client.stream_command("localhost:9999",frame_count, delay_time)
	end = time()
	#for frame in attempt["returned"]:
	#	print("{},{},{}".format(frame.id,frame.data[0],frame.data[1]))
	print("Time: {}s for {} frames".format(end-start,frame_count))
	server.exit()
	sleep(1)
