"""Run real KiCad checks and preserve all findings, including unrouted pads."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import collections
import json
import os
import subprocess
import argparse
import hashlib
from design import OUT, boards

CLI=os.environ.get('SKYWAVE_KICAD_CLI',str(Path.home()/'.local/bin/kicad10-cli-skysentinel'))
ECAD=OUT/'ecad';REPORT=OUT/'reports'

def one(board):
    name=board.name;result={}
    for kind in ['erc','drc']:
        output=REPORT/(name+'_'+kind+'.json')
        cmd=[CLI,'sch' if kind=='erc' else 'pcb',kind,'--format','json','--severity-all','-o',str(output),str(ECAD/(name+('.kicad_sch' if kind=='erc' else '.kicad_pcb')))]
        run=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        result[kind+'_returncode']=run.returncode
        if not output.exists():raise RuntimeError(run.stderr+run.stdout)
        data=json.loads(output.read_text())
        violations=[v for s in data.get('sheets',[]) for v in s.get('violations',[])] if kind=='erc' else data.get('violations',[])
        result[kind]=dict(collections.Counter(v['severity']+':'+v['type'] for v in violations))
        if kind=='drc':
            result['unconnected']=len(data.get('unconnected_items',[]))
    result['board_sha256']=hashlib.sha256((ECAD/(name+'.kicad_pcb')).read_bytes()).hexdigest()
    result['schematic_sha256']=hashlib.sha256((ECAD/(name+'.kicad_sch')).read_bytes()).hexdigest()
    result['connectivity_and_clearance_passed']=not result['unconnected'] and not any(
        key.startswith('error:') for kind in ['erc','drc'] for key in result[kind])
    result['production_released']=False
    return name,result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('names',nargs='*');args=parser.parse_args()
    REPORT.mkdir(exist_ok=True,parents=True)
    summary=REPORT/'checks.json'
    result=json.loads(summary.read_text()) if args.names and summary.exists() else {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        result.update(dict(pool.map(one,[b for b in boards() if not args.names or b.name in args.names])))
    (REPORT/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if any(not result[b.name].get('connectivity_and_clearance_passed') for b in boards() if not args.names or b.name in args.names):
        raise SystemExit('ERC/DRC connectivity or clearance check failed; see preserved reports.')
