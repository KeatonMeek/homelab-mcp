"""Fixed read-only host collector. No input arguments; never emits raw logs/secrets."""
import argparse
import collections
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile

MOUNTS = ['/']
INCLUDE_DOCKER = False
ENV = {'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':'/nonexistent'}


def command(args, timeout=12):
    try:
        p=subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=ENV)
        if p.returncode: return None, 'unavailable_or_permission_denied'
        if len(p.stdout)>2_000_000:return None,'output_limit'
        return p.stdout,None
    except (OSError,subprocess.TimeoutExpired):return None,'unavailable_or_timeout'


def docker():
    if not INCLUDE_DOCKER:
        return {'available': False, 'error': 'disabled_by_configuration'}
    out,error=command(['/usr/bin/docker','ps','-a','--format','{{.ID}}'])
    if error:return {'available':False,'error':error}
    ids=out.splitlines()[:100]
    if not ids:return {'available':True,'containers':[],'truncated':False}
    fmt='{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Config.Image}},"state":{{json .State.Status}},"running":{{json .State.Running}},"exit_code":{{json .State.ExitCode}},"oom_killed":{{json .State.OOMKilled}},"restart_count":{{json .RestartCount}},"started_at":{{json .State.StartedAt}},"restart_policy":{{json .HostConfig.RestartPolicy.Name}},"health":{{$health := index .State "Health"}}{{if $health}}{{json $health.Status}}{{else}}null{{end}}}'
    detail,error=command(['/usr/bin/docker','inspect','--format',fmt,*ids])
    if error:return {'available':False,'error':error}
    return {'available':True,'containers':[json.loads(x) for x in detail.splitlines()],
            'truncated':len(out.splitlines())>100}


def storage():
    result=[]
    for path in MOUNTS:
        if not Path(path).exists():
            result.append({'mount':path,'available':False});continue
        s=os.statvfs(path)
        total=s.f_blocks*s.f_frsize;free=s.f_bavail*s.f_frsize
        used=(s.f_blocks-s.f_bfree)*s.f_frsize
        result.append({'mount':path,'available':True,'is_mount':os.path.ismount(path),
            'total_bytes':total,'available_bytes':free,'used_percent':round(100*used/(used+free),1) if used+free else 0,
            'inodes_total':s.f_files,'inodes_available':s.f_favail,
            'inode_used_percent':round(100*(s.f_files-s.f_ffree)/s.f_files,1) if s.f_files else 0,
            'read_only':bool(s.f_flag & os.ST_RDONLY)})
    return result


def system():
    mem={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        k,_,v=line.partition(':')
        if k in ['MemTotal','MemAvailable','SwapTotal','SwapFree']:mem[k]=int(v.split()[0])*1024
    pressure={}
    for kind in ['cpu','memory','io']:
        p=Path('/proc/pressure')/kind
        if p.exists():
            pressure[kind]={}
            for line in p.read_text().splitlines():
                fields=line.split();pressure[kind][fields[0]]={k:float(v) for k,v in (f.split('=') for f in fields[1:]) if k!='total'}
    out,error=command(['/usr/bin/systemctl','list-units','--failed','--no-legend','--plain','--no-pager'])
    return {'hostname':os.uname().nodename,'uptime_seconds':float(Path('/proc/uptime').read_text().split()[0]),
        'load_1_5_15':list(os.getloadavg()),'logical_cpus':os.cpu_count(),'memory_bytes':mem,'pressure':pressure,
        'failed_units':None if error else [l.split()[0] for l in out.splitlines() if l.strip()][:50],
        'failed_units_error':error}


def logs():
    out,error=command(['/usr/bin/journalctl','--since','-15min','--priority=0..3','--lines=200',
        '--no-pager','--quiet','--output=json','--output-fields=PRIORITY,_SYSTEMD_UNIT,_TRANSPORT'])
    if error:return {'available':False,'error':error}
    entries=[json.loads(l) for l in out.splitlines() if l.strip()]
    counts=collections.Counter(str(e.get('_SYSTEMD_UNIT','unattributed'))[:128] for e in entries)
    return {'available':True,'window_minutes':15,'sample_limit':200,'sampled_errors':len(entries),
        'possibly_truncated':len(entries)==200,'by_unit':dict(counts.most_common(30)),
        'coverage':'journald entries visible to the collector OS account; no message payloads collected'}


def network():
    out,error=command(['/usr/bin/ss','-H','-lntu'])
    listeners=[]
    if not error:
        for line in out.splitlines()[:100]:
            f=line.split()
            if len(f)<5:continue
            address,_,port=f[4].rpartition(':')
            if not port.isdigit():continue
            scope='loopback' if address.strip('[]') in ['127.0.0.1','::1'] or address.startswith('127.') else 'wildcard' if address in ['*','0.0.0.0','[::]'] else 'specific_address'
            listeners.append({'protocol':f[0],'port':int(port),'binding':scope})
    interfaces=[]
    for line in Path('/proc/net/dev').read_text().splitlines()[2:]:
        name,_,values=line.partition(':');v=values.split()
        if len(v)>=12:
            interfaces.append({'name':name.strip()[:64],'rx_errors':int(v[2]),'rx_dropped':int(v[3]),'tx_errors':int(v[10]),'tx_dropped':int(v[11])})
    return {'listeners':listeners,'listeners_truncated':bool(out and len(out.splitlines())>100),'listener_error':error,'interfaces':interfaces[:64],
        'firewall':'not inspected: requires additional privileges; no firewall rules exposed'}


def collect():
    data={'schema_version':1,'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    for key,fn in [('system',system),('docker',docker),('storage',storage),('logs',logs),('network',network)]:
        try:data[key]=fn()
        except Exception:data[key]={'available':False,'error':'collection_failed'}
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Absolute snapshot file outside the checkout')
    parser.add_argument('--mount', action='append', help='Absolute filesystem path; repeatable, default /')
    parser.add_argument('--docker', action='store_true', help='Query Docker using existing OS permissions; often root-equivalent')
    args = parser.parse_args()
    global MOUNTS, INCLUDE_DOCKER
    MOUNTS = args.mount or ['/']
    INCLUDE_DOCKER = args.docker
    if not args.output.is_absolute() or any(not Path(p).is_absolute() for p in MOUNTS):
        parser.error('Paths must be absolute')
    if len(MOUNTS) > 32:
        parser.error('At most 32 mounts')
    DEST = args.output.parent
    os.umask(0o077)
    DEST.mkdir(mode=0o700,exist_ok=True)
    if any(p.is_symlink() for p in [DEST, *DEST.parents]) or DEST.stat().st_uid != os.getuid() or DEST.stat().st_mode & 0o077:
        raise RuntimeError('Snapshot directory must be private and owned by this OS account')
    raw=json.dumps(collect(),ensure_ascii=True,allow_nan=False)
    if len(raw)>262144:raise RuntimeError('Snapshot limit exceeded')
    fd,name=tempfile.mkstemp(dir=DEST,prefix='.health-',suffix='.tmp')
    with os.fdopen(fd,'w') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(name,args.output)
    print('Sanitized health snapshot updated.')


if __name__=='__main__':main()
