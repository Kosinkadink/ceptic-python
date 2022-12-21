import pytest

from fixtures.locations import locations

from fixtures.client import client_all_files
from fixtures.client import client_cafile_only
from fixtures.client import client_certfile_keyfile_only
from fixtures.client import client_no_files
from fixtures.client import client_not_secure

from fixtures.server import server_all_files
from fixtures.server import server_certfile_keyfile_only
from fixtures.server import server_not_secure
