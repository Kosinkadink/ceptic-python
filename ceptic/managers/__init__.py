from sys import version_info
if version_info < (3,0): # python2 code
	import certificatemanager
	import endpointmanager
	import streammanager
else:
	import ceptic.managers.certificatemanager
	import ceptic.managers.endpointmanager
	import ceptic.managers.streammanager
