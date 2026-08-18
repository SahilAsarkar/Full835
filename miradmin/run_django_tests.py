import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'django_backend')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'onesmarter_admin.settings')

import django
django.setup()

from django.test.utils import get_runner
from django.conf import settings

if __name__ == '__main__':
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False)
    failures = test_runner.run_tests(['api.tests'])
    sys.exit(bool(failures))
