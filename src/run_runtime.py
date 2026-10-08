"""Pinned runtime evidence for reproducible experiment entry points."""
import importlib.metadata
import platform
import sys
from pathlib import Path

def checked_environment(requirements):
    pairs=[line.strip().split('==') for line in Path(requirements).read_text().splitlines() if '==' in line and not line.lstrip().startswith('#')]
    installed={name:importlib.metadata.version(name) for name,_ in pairs}
    if sys.version_info[:2]!=(3,12):raise RuntimeError('Experiments require Python 3.12')
    mismatches={name:{'expected':expected,'installed':installed[name]} for name,expected in pairs if installed[name]!=expected}
    if mismatches:raise RuntimeError('Dependency versions differ from pinned requirements: '+str(mismatches))
    return {'python':sys.version,'platform':platform.platform(),'dependencies':installed,'pinned_versions_verified':True}
