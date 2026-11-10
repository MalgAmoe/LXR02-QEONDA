#!/usr/bin/env python3
"""Single-file project integration replaces legacy glo.cfg persistence tests."""
from pathlib import Path
import runpy, sys
sys.argv = [str(Path(__file__).with_name('test_project_runtime.py')), 'persistence']
runpy.run_path(sys.argv[0], run_name='__main__')
