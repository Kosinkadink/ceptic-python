from sys import version_info
if version_info < (3,0): # python2 code
	import certificatemanager
	import databasemanager
	import endpointmanager
	import filemanager
	import loggermanager
	import processmanager
	import protocolmanager
	import sessionmanager
	import streammanager
	import terminalmanager
else:
	import ceptic.managers.certificatemanager
	import ceptic.managers.databasemanager
	import ceptic.managers.endpointmanager
	import ceptic.managers.filemanager
	import ceptic.managers.loggermanager
	import ceptic.managers.processmanager
	import ceptic.managers.protocolmanager
	import ceptic.managers.sessionmanager
	import ceptic.managers.streammanager
	import ceptic.managers.terminalmanager
