"""WSGI configuration for PythonAnywhere.

Open the Web tab, click the WSGI file link, delete what is there and paste this
in. Replace USERNAME with your PythonAnywhere username and, if you cloned into a
different folder, the folder name too. Then press Reload.
"""

import sys
from pathlib import Path

PROJECT = Path("/home/USERNAME/scholaris")
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from run import app as application  # noqa: E402
