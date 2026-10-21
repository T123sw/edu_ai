"""Render offline; native authoring can use network without host credentials or private files.

The full upstream CLI stays unmodified. Linux bubblewrap provides the boundary;
without it generation fails closed, rather than evaluating model HTML on the host.
"""
import os
from pathlib import Path
import shutil
import sys


def isolated_command(command, *, runtime, project, read_only_roots=(), network=False):
    binary = os.environ.get('HYPERFRAMES_BWRAP_PATH') or shutil.which('bwrap')
    if sys.platform != 'linux' or not binary or not Path(binary).is_file():
        raise RuntimeError('Native rendering requires Linux bubblewrap: install bubblewrap or use the isolated Linux worker')
    project = Path(project).resolve()
    runtime = Path(runtime).resolve()
    node = Path(command[0]).resolve()
    args = [binary, '--unshare-all', '--die-with-parent', '--new-session']
    if network:
        args += ['--share-net']
    mounts = ['/usr', '/lib', '/lib64']
    for value in mounts:
        if Path(value).exists(): args += ['--ro-bind', value, value]
    args += ['--symlink','usr/bin','/bin','--symlink','usr/sbin','/sbin',
             '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/etc']
    for value in ('/etc/fonts','/etc/localtime'):
        if Path(value).exists(): args += ['--ro-bind',value,value]
    # Conda Node links shared libraries from its own prefix.
    if not str(node).startswith('/usr/'):
        prefix = node.parent.parent
        args += ['--ro-bind', str(prefix), str(prefix)]
    browser = os.environ.get('HYPERFRAMES_BROWSER_PATH')
    if browser:
        directory = Path(browser).resolve().parent
        args += ['--ro-bind',str(directory),str(directory)]
    else:
        for relative in ('.cache/hyperframes/chrome', '.cache/puppeteer'):
            cache = Path.home()/relative
            if cache.exists(): args += ['--ro-bind',str(cache),str(cache)]
    args += ['--ro-bind',str(runtime),str(runtime),'--bind',str(project),str(project),
             '--chdir',str(project)]
    for root in read_only_roots:
        args += ['--ro-bind',str(root),str(root)]
    if network:
        for name in ('/etc/resolv.conf', '/etc/ssl', '/etc/hosts'):
            if Path(name).exists(): args += ['--ro-bind',name,name]
    args += ['--',*map(str,command)]
    keep = ('PATH','HOME','LANG','LC_ALL','HYPERFRAMES_BROWSER_PATH','PRODUCER_BROWSER_GPU_MODE')
    environment = {k:os.environ[k] for k in keep if k in os.environ}
    environment.setdefault('PRODUCER_BROWSER_GPU_MODE','software')
    environment.update(HYPERFRAMES_NO_TELEMETRY='1',DO_NOT_TRACK='1',CI='true',TMPDIR='/tmp',HYPERFRAMES_HISTORY_ROOT=str(project/'.hyperframes/history'))
    return args, environment
