import os
from sql_mode.support import load_package_tests, import_module

# Skip tests if we don't have threading.
import_module('threading')
# Skip tests if we don't have concurrent.futures.
import_module('concurrent.futures')

def load_tests(*args):
    return load_package_tests(os.path.dirname(__file__), *args)
