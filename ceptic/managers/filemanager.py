import os


class FileManager(object):
    """
    Used to manage CEPtic implementation files
    """

    def __init__(self, location, create_immediately=True):
        self.__location__ = location
        self.locations = {
            "root": self.__location__,
            "resources": os.path.join(self.__location__, "resources"),
            "protocols": os.path.join(os.path.join(self.__location__, "resources"), "protocols"),
            "cache": os.path.join(os.path.join(self.__location__, "resources"), "cache"),
            "programparts": os.path.join(os.path.join(self.__location__, "resources"), "programparts"),
            "uploads": os.path.join(os.path.join(self.__location__, "resources"), "uploads"),
            "downloads": os.path.join(os.path.join(self.__location__, "resources"), "downloads"),
            "networkpass": os.path.join(os.path.join(self.__location__, "resources"), "networkpass"),
            "certification": os.path.join(os.path.join(self.__location__, "resources"), "certification")
        }
        if create_immediately:
            self.create_directories()

    def create_directories(self):
        """
        Create general CEPtic implementation directories
        :return: None
        """
        if not os.path.exists(self.locations["resources"]): os.makedirs(self.locations["resources"])
        if not os.path.exists(self.locations["protocols"]): os.makedirs(self.locations["protocols"])
        if not os.path.exists(self.locations["cache"]): os.makedirs(self.locations["cache"])
        if not os.path.exists(self.locations["programparts"]): os.makedirs(self.locations["programparts"])
        if not os.path.exists(self.locations["uploads"]): os.makedirs(self.locations["uploads"])
        if not os.path.exists(self.locations["downloads"]): os.makedirs(self.locations["downloads"])
        if not os.path.exists(self.locations["networkpass"]): os.makedirs(self.locations["networkpass"])
        if not os.path.exists(self.locations["certification"]): os.makedirs(self.locations["certification"])

    def add_directory(self, key, location, base_key=None):
        """
        Add more CEPtic implementation directory bindings
        :param key: string key
        :param location: directory of binding; relative or absolute
        :param base_key: optional existing dictionary key to reference for start of path
        :return: None
        """
        if base_key is not None and base_key in self.locations:
            location = os.path.join(self.locations[base_key], location)
        else:
            if not location.startswith(self.locations["resources"]):
                location = os.path.join(self.locations["resources"], location)
        # try to create directory
        if not os.path.exists(location): os.makedirs(location)
        # add it to dictionary
        self.locations[key] = location

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

    def add_file(self, key, location, base_key=None, text=""):
        """
        Add file location bindings to CEPtic implementation directory bindings
        :param key: string key
        :param location: directory of binding; relative or absolute
        :param base_key: optional existing dictionary key to reference for start of path
        :param text: optional text/bytes to place in file if doesnt exist
        :return: None
        """
        if base_key is not None and base_key in self.locations:
            location = os.path.join(self.locations[base_key], location)
        else:
            if not location.startswith(self.locations["resources"]):
                location = os.path.join(self.locations["resources"], location)
        # try to create empty file if doesn't exist
        if not os.path.exists(location):
            with open(location, "wb") as seeds:
                seeds.write(text)
        # add it to dictionary
        self.locations[key] = location

    def get_netpass(self, passfilename="default.txt"):
        """
        Returns netpass from specified file in networkpass directory, default.txt by default
        :param passfilename: some .txt filename such as "notdefault.txt", or blank
        :return: network password (string)
        """
        if not os.path.exists(os.path.join(self.locations["networkpass"], passfilename)):
            with open(os.path.join(self.locations["networkpass"], passfilename),
                      "a") as protlist:  # file used for identifying what protocols are available
                pass
            netpass = None
        else:
            with open(os.path.join(self.locations["networkpass"], passfilename),
                      "r") as protlist:  # file used for identifying what protocols are available
                netpassword = protlist.readline().strip()
            if netpassword != '':
                netpass = netpassword
            else:
                netpass = None
        return netpass
