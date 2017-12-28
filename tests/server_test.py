from testingfixtures import add_surrounding_dir_to_path
# add surrounding dir to path to enable importing
add_surrounding_dir_to_path()

from ceptic.server import CepticServerTemplate, main
from ceptic.common import normalize_path, decode_unicode_hook, FileFrame
from ceptic.managers.streammanager import StreamManager, StreamFrame
from shutil import rmtree, copytree
from time import sleep
from hashlib import sha1
from threading import Thread
import json
import sys
import os


class ExampleServer(CepticServerTemplate):

	def __init__(self, location, start_terminal=True, block_on_start=False):
		name = "test"
		version = "3.0.0"
		CepticServerTemplate.__init__(self, location, start_terminal=start_terminal, server=9999, name=name, version=version, block_on_start=block_on_start)

	def add_terminal_commands(self):
		self.terminalManager.add_command("ping", lambda data: self.ping_terminal_command(data[1]))

	def add_endpoint_commands(self):
		self.endpointManager.add_command("send", self.send_file_request_endpoint)
		self.endpointManager.add_command("recv", self.recv_file_request_endpoint)
		self.endpointManager.add_command("stream", self.stream_request_endpoint)

	def send_file_request_endpoint(self, s, data=None):
		file_name = data["filename"]
		file_path = os.path.join(self.fileManager.get_directory("downloads"),file_name)
		fileframe = FileFrame(file_name, file_path, send_cache=self.get_cache_size())
		try:
			return_data = json.dumps(fileframe.recv(s))
		except IOError:
			return_data = json.dumps({"status": 400, "msg": "IOError occurred"})
		print("SERVER: {}".format(type(s)))
		print("SERVER: {}".format(return_data))
		s.sendall(return_data)
		return return_data

	def recv_file_request_endpoint(self, s, data=None):
		file_name = data["filename"]
		file_path = os.path.join(self.fileManager.get_directory("uploads"),file_name)
		fileframe = FileFrame(file_name, file_path, send_cache=self.get_cache_size())
		try:
			return_data = json.dumps(fileframe.send(s))
		except IOError:
			return_data = json.dumps({"status": 400, "msg": "IOError occurred"})
		print("SERVER: {}".format(type(s)))
		print("SERVER: {}".format(return_data))
		s.sendall(return_data)
		return return_data

	def stream_request_endpoint(self, s, data=None, data_to_store=None):
		# start the stream
		print("SERVER: starting stream manager...")
		stream = StreamManager(s, remove_on_send=False)
		stream.start()
		print("SERVER: stream manager started!")
		# if shouldn't stop, keep processing frames
		frame_count = 0
		while not self.shouldExit:
			# if received frame to process, read it and process it
			if stream.is_ready_to_read():
				#print("SERVER: frame ready to receive!")
				frame = stream.get_ready_to_read()
				#print("id: {}, data: {}".format(frame.id,frame.data))
				number = json.loads(frame.data[0],object_pairs_hook=decode_unicode_hook)["number"]
				#print("SERVER: number in frame is {}".format(number))
				# square the number as the reponse
				response = {"number": number**2}
				#print("SERVER: response saved as {}".format(str(response)))
				frame.data[0] = None
				frame.data[1] = json.dumps(response)
				# send frame back
				stream.add(frame)
				#print("SERVER: frame send back! {}".format(frame_count))
				frame_count += 1



# TESTS:

def test_creation():

	server = ExampleServer(location=test_creation.test_location,start_terminal=False)
	server.start()
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
		"resources/certification/techtem_key_server.pem"
	]
	# list of files that shoudl NOT exist
	not_files = [
		"resources/certification/techtem_key_client.pem"
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
	function.archive_certification_dir = os.path.join(function.test_dir,"server_certs/certification")
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
