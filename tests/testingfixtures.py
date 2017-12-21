import os
import sys


def add_surrounding_dir_to_path():
	# get main directory
	__location__ = os.path.join(os.path.realpath(
	    os.path.join(os.getcwd(), os.path.dirname(__file__))), "..")
	# add it to sys path for imports to work
	sys.path.insert(0, os.path.join(__location__))
	# import project-level modules
