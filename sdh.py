import sys
import inspect
import os

sdh_root_directory = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(1, sdh_root_directory)

import _sdh

