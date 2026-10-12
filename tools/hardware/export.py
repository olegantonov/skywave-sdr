"""Export review PDFs/netlists and gated prototype manufacturing plots."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import subprocess
import hashlib
from check import CLI
from design import OUT, boards

def export(name,manufacturing=False):
    ecad=OUT/'ecad';pdf=OUT/'plots';pdf.mkdir(exist_ok=True)
    commands=[['sch','export','netlist','--format','kicadxml','-o',str(ecad/(name+'.net')),str(ecad/(name+'.kicad_sch'))],
        ['sch','export','pdf','-o',str(pdf/(name+'_schematic.pdf')),str(ecad/(name+'.kicad_sch'))],
        ['pcb','export','svg','--layers','F.Cu,F.SilkS,F.Fab,Edge.Cuts','--page-size-mode','2','-o',str(pdf/(name+'_pcb.svg')),str(ecad/(name+'.kicad_pcb'))]]
    if manufacturing:
        summary=json.loads((OUT/'reports/checks.json').read_text())[name]
        if summary.get('board_sha256')!=hashlib.sha256((ecad/(name+'.kicad_pcb')).read_bytes()).hexdigest():
            raise RuntimeError(name+': rerun checks; DRC summary does not match the board')
        if not summary.get('connectivity_and_clearance_passed'):
            raise RuntimeError(name+': circuit/layout checks have not passed')
        drc=json.loads((OUT/'reports'/(name+'_drc.json')).read_text())
        if drc['unconnected_items'] or any(v['severity']=='error' for v in drc['violations']):
            raise RuntimeError(name+': manufacturing export blocked by DRC errors or unrouted connections')
        target=OUT/'fabrication_prototype'/name;target.mkdir(parents=True,exist_ok=True)
        layers='F.Cu,B.Cu,F.Paste,B.Paste,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts'
        if name!='control':layers+=',In1.Cu,In2.Cu'
        commands += [['pcb','export','gerbers','--layers',layers,'--subtract-soldermask','-o',str(target),str(ecad/(name+'.kicad_pcb'))],
            ['pcb','export','drill','-o',str(target)+'/',str(ecad/(name+'.kicad_pcb'))]]
    for cmd in commands:
        r=subprocess.run([CLI,*cmd],capture_output=True,text=True,timeout=150)
        if r.returncode:raise RuntimeError(' '.join(cmd)+'\n'+r.stderr+r.stdout)
    return name

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manufacturing',action='store_true');p.add_argument('names',nargs='*');args=p.parse_args()
    with ThreadPoolExecutor(max_workers=2) as pool:
        for name in pool.map(lambda n:export(n,args.manufacturing),args.names or [b.name for b in boards()]):print(name)
