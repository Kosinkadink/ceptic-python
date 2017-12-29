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


def setup_client():
	testfiles_clientname = "testfilesclient"
	test_dir = os.path.join(os.path.realpath(
		os.path.join(os.getcwd(), os.path.dirname(__file__))))
	test_clientlocation = os.path.join(test_dir,testfiles_clientname)
	resource_clientdir = os.path.join(test_clientlocation,"resources")
	actual_certification_clientdir = os.path.join(resource_clientdir, "certification")
	archive_client_certification_dir = os.path.join(test_dir,"client_certs/certification")
	try:
		copytree(archive_client_certification_dir,actual_certification_clientdir)
	except OSError:
		pass
	return test_clientlocation


if __name__ == "__main__":
	location = setup_client()

	client = ExampleClient(location=location,start_terminal=False)
	frame_count = 8000
	send_delay = 0
	start = time()
	attempt = client.stream_command("localhostdad:9999",frame_count,send_delay)
	end = time()
	print(attempt)
	#for frame in attempt["returned"]:
	#	print("{},{},{}".format(frame.id,frame.data[0],frame.data[1]))
	print("Time: {}s for {} frames".format(end-start,frame_count))

