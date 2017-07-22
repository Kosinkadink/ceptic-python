import os


class FileManager(object):
    """
    Used to manage CEPtic implementation files
    """

    def __init__(self, location):
        self.__location__ = location
        self.locations = {
            "resources": os.path.join(self.__location__, "resources"),
            "protocols": os.path.join(self.locations["resources"], "protocols"),
            "cache": os.path.join(self.locations["resources"], "cache"),
            "programparts": os.path.join(self.locations["resources"], "programparts"),
            "uploads": os.path.join(self.locations["resources"], "uploads"),
            "downloads": os.path.join(self.locations["resources"], "downloads"),
            "networkpass": os.path.join(self.locations["resources"], "networkpass"),
            "certification": os.path.join(self.locations["resources"], "certification")
        }
        self.create_directories()

    def create_directories(self):
        """
        Create general CEPtic implementation directories
        :return: 
        """
        if not os.path.exists(self.locations["resources"]): os.makedirs(self.locations["resources"])
        if not os.path.exists(self.locations["protocols"]): os.makedirs(self.locations["protocols"])
        if not os.path.exists(self.locations["cache"]): os.makedirs(self.locations["cache"])
        if not os.path.exists(self.locations["programparts"]): os.makedirs(self.locations["programparts"])
        if not os.path.exists(self.locations["uploads"]): os.makedirs(self.locations["uploads"])
        if not os.path.exists(self.locations["downloads"]): os.makedirs(self.locations["downloads"])
        if not os.path.exists(self.locations["networkpass"]): os.makedirs(self.locations["networkpass"])
        if not os.path.exists(self.locations["certification"]): os.makedirs(self.locations["certification"])

    def add_directory(self, key, location):
        """
        Add more CEPtic implementation directory bindings
        :param key: string key
        :param location: directory of binding; if doesn't start with slash, relative to resources
        :return: 
        """
        if not location.startswith(self.locations["resources"]):
            location = os.path.join(self.locations["resources"], location)
        self.locations[key] = location
        if not os.path.exists(location): os.makedirs(location)

    def get_directory(self, key):
        """
        Return directory, if exists
        :param key: string key
        :return: directory bound to location key
        """
        if key in self.locations:
            return self.locations[key]
        else:
            return None
