"""Remove only unused track/via stubs identified by the real KiCad DRC."""
import json
import sys
import sexpdata
import pcbnew as pcb
from ecad import ECAD,vec
from design import OUT
from route import restore_rules

for name in sys.argv[1:]:
    report=json.loads((OUT/'reports'/(name+'_drc.json')).read_text())
    ids={item['uuid'] for v in report['violations'] if v['type'] in ('track_dangling','via_dangling') for item in v['items']}
    path=ECAD/(name+'.kicad_pcb');tree=sexpdata.loads(path.read_text());removed=0
    clean=[]
    for item in tree:
        if isinstance(item,list) and str(item[0]) in ('segment','via') and any(isinstance(x,list) and str(x[0]) in ('tstamp','uuid') and str(x[1]) in ids for x in item):
            removed+=1;continue
        clean.append(item)
    path.write_text('('+str(clean[0])+'\n'+'\n'.join(sexpdata.dumps(x) for x in clean[1:])+')\n');board=pcb.LoadBoard(str(path))
    if name=='control':
        positions={'RV1':(66,72),'SW2':(35,50),'J7':(41,83)}
        for f in board.GetFootprints():
            if f.GetReference() in positions:f.Reference().SetPosition(vec(*positions[f.GetReference()]))
        for item in board.GetDrawings():
            if isinstance(item,pcb.PCB_TEXT):item.SetPosition(vec(30,97))
    board.BuildConnectivity();pcb.ZONE_FILLER(board).Fill(board.Zones());pcb.SaveBoard(str(path),board);restore_rules(name)
    print(name,'removed unused items:',removed)
