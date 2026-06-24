"""urirun node — Android foreground service entry point.

p4a starts this script in a separate process as a foreground Android service
(declared via android.services in buildozer.spec).  The foreground notification
prevents Android from killing the process when the Kivy activity is backgrounded,
which is why the HTTP server runs here rather than in the activity.
"""

import os
import sys
import time

# Allow imports from the parent directory (main.py lives there)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

from main import DEFAULT_PORT, UriNodeServer, UriRuntime  # noqa: E402

runtime = UriRuntime(DEFAULT_PORT)
server = UriNodeServer(runtime, port=DEFAULT_PORT)
server.start()

runtime.log("service-started", pid=os.getpid())

# Block here; the service lives as long as this script is running.
while True:
    time.sleep(10)
