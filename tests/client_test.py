from testingfixtures import add_surrounding_dir_to_path
# add surrounding dir to path to enable importing
add_surrounding_dir_to_path()

from ceptic.client import CepticClientTemplate, main
from ceptic.common import normalize_path, decode_unicode_hook, FileFrame
from shutil import rmtree, copytree
from time import sleep
from hashlib import sha1
import sys
import os
import json


class ExampleClient(CepticClientTemplate):

	def __init__(self, location, start_terminal):
		name = "test"
		version = "3.0.0"
		CepticClientTemplate.__init__(self, location, start_terminal, name=name, version=version)

	def add_terminal_commands(self):
		self.terminalManager.add_command("ping", lambda data: self.ping_terminal_command(data[1]))

	def add_endpoint_commands(self):
		self.endpointManager.add_command("send", self.send_file_endpoint)
		self.endpointManager.add_command("recv", self.recv_file_endpoint)

	def send_file_command(self, ip, filename):
		return self.connect_ip(ip, {"filename": filename}, "send")

	def recv_file_command(self, ip, filename):
		return self.connect_ip(ip, {"filename": filename}, "recv")

	def send_file_endpoint(self, s, data=None, data_to_store=None):
		# send file
		file_name = data["filename"]
		file_path = os.path.join(self.fileManager.get_directory("uploads"),file_name)
		fileframe = FileFrame(file_name, file_path, send_cache=self.get_cache_size())
		try:
			success_data = fileframe.send(s)
			print("CLIENT: {}".format(type(s)))
			if success_data["status"] != 200:
				return_data = success_data
			else:
				return_data = json.loads(s.recv(128),object_pairs_hook=decode_unicode_hook)
		except IOError as e:
			return_data = {"status": 444, "msg": "IOError here: {}".format(str(e))}
		return return_data

	def recv_file_endpoint(self, s, data=None, data_to_store=None):
		# send file
		file_name = data["filename"]
		file_path = os.path.join(self.fileManager.get_directory("downloads"),file_name)
		fileframe = FileFrame(file_name, file_path, send_cache=self.get_cache_size())
		try:
			success_data = fileframe.recv(s)
			print("CLIENT: {}".format(type(s)))
			if success_data["status"] != 200:
				return_data = success_data
			else:
				return_data = json.loads(s.recv(128),object_pairs_hook=decode_unicode_hook)
		except IOError as e:
			return_data = {"status": 444, "msg": "IOError here: {}".format(str(e))}
		return return_data

# TESTS:

def test_creation():

	client = ExampleClient(location=test_creation.test_location,start_terminal=False)
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
	# list of directories that should NOT exist
	not_directories = [
	]
	# list of files that should exist
	files = [
		"resources/certification/techtem_cert_client.pem",
		"resources/certification/techtem_cert_server.pem",
		"resources/certification/techtem_key_client.pem"
	]
	# list of files that shoudl NOT exist
	not_files = [
		"resources/certification/techtem_key_server.pem"
	]
	# check if directories exist
	for directory in directories:
		fullpath = os.path.join(test_creation.test_location,directory)
		print(fullpath)
		assert os.path.isdir(fullpath)
	# check if directories DON'T exist
	for directory in not_directories:
		fullpath = os.path.join(test_creation.test_location,directory)
		print(fullpath)
		assert not os.path.isdir(fullpath)
	# check if files exist
	for file in files:
		fullpath = os.path.join(test_creation.test_location,file)
		print(fullpath)
		assert os.path.isfile(fullpath)
	# check if files DON'T exist
	for file in not_files:
		fullpath = os.path.join(test_creation.test_location,file)
		print(fullpath)
		assert not os.path.isfile(fullpath)

# END TESTS


# set up for each function
def setup_function(function):
	testfiles_name = "testfiles"
	function.test_dir = os.path.join(os.path.realpath(
		os.path.join(os.getcwd(), os.path.dirname(__file__))))
	function.test_location = os.path.join(function.test_dir,testfiles_name)
	resource_dir = os.path.join(function.test_location,"resources")
	function.actual_certification_dir = os.path.join(resource_dir, "certification")
	function.archive_certification_dir = os.path.join(function.test_dir,"client_certs/certification")
	copytree(function.archive_certification_dir,function.actual_certification_dir)

def teardown_function(function):
	# remove everything BUT the resources/certification directory
	rmtree(function.test_location)

# done setting up objects for each module


# setup objects for this module
def setup_module(module):
	pass

def teardown_module(module):
	pass

# done setting up objects for this module
