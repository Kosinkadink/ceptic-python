import os
import sys


class ProtocolManager(object):
    """
    Used to manage CEPtic client protocols loaded into client/server instance
    """
    def __init__(self, location, import_auto=True):
        self.__location__ = location
        self.available = set()
        self.protocols = {}
        self.loadedProtocols = {}
        self.gen_available_protocols(import_auto)

    def add_to_available(self, name):
        self.available.add(name)

    def check_if_available(self, name):
        return name in self.available

    def get_available_list(self):
        return sorted(self.available)

    def clear_protocols(self):
        for prot in self.available:
            self.remove_protocol(prot)
        self.available.clear()

    def add_protocol(self, name, prot):
        self.protocols[name] = prot

    def remove_protocol(self, name):
        if name in self.protocols:
            self.unload_protocol(name)
            self.protocols.pop(name, None)
            return True
        else:
            return False

    def get_protocol(self, name):
        return self.protocols.get(name, None)

    def get_loaded_protocol_object(self, name):
        return self.loadedProtocols.get(name, None)

    def load_protocol(self, name, location):
        if name in self.protocols and name not in self.loadedProtocols:
            self.loadedProtocols[name] = self.protocols[name].TemplateProt(location, startTerminal=False)
            return self.loadedProtocols.get(name)
        elif name in self.loadedProtocols:
            return self.loadedProtocols.get(name)
        else:
            return None

    def unload_protocol(self, name):
        if name in self.loadedProtocols:
            self.loadedProtocols[name].exit()
            self.loadedProtocols.pop(name, None)
            return True
        else:
            return False

    def gen_available_protocols(self, import_auto=True):
        protocols_dir = os.path.join(self.__location__, "resources/protocols/")
        for file in os.listdir(protocols_dir):
            if file.endswith(".py"):
                prot = file[:-3]
                self.add_to_available(prot)
                if import_auto:
                    self.import_manual(prot)

    def import_manual(self, name):
        if name in self.available:
            filename = self.__location__ + '/resources/protocols/' + name + '.py'
            directory, module_name = os.path.split(filename)
            module_name = os.path.splitext(module_name)[0]

            path = list(sys.path)
            sys.path.insert(0, directory)
            try:
                module_imported = __import__(module_name)  # cool import command
            except Exception, e:
                raise e
            else:
                self.add_protocol(module_name, module_imported)
            finally:
                sys.path[:] = path
