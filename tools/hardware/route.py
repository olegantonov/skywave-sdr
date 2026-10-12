"""Prepare DSN rules, import router sessions and add ground planes."""
import argparse
import re
import json
import sexpdata
import pcbnew as pcb
from ecad import ECAD, mm, vec
from design import boards

def prepare(name):
    path=ECAD/(name+'.dsn')
    s=path.read_text()
    s=re.sub(r'(\(layer In[12]\.Cu\s+\(type )signal',r'\1power',s)
    # Fine-pitch QFN escapes require 0.15 mm spacing and 0.20 mm tracks.
    s=s.replace('(clearance 200.1)','(clearance 150)')
    match=re.search(r'    \(class kicad_default.*?\n    \)\n  \)\n  \(wiring',s,re.S)
    if not match:raise ValueError('DSN class missing')
    block=match.group(0)
    powers=re.findall(r'\+\w+',block.split('(circuit')[0])
    for net in powers:block=re.sub(r'(?<!\S)'+re.escape(net)+r'(?!\S)','',block)
    classes=''
    for i,net in enumerate(powers):
        width=500 if net in ('+5V','+4V') else 300
        classes+=f'    (class supply{i} {net} (circuit (use_via Via[0-{3 if name!="control" else 1}]_600:300_um)) (rule (width {width}) (clearance 150)))\n'
    block=block.replace('  )\n  (wiring',classes+'  )\n  (wiring')
    s=s[:match.start()]+block+s[match.end():]
    path.write_text(s)

def finish(spec):
    path=ECAD/(spec.name+'.kicad_pcb')
    tree=sexpdata.loads(path.read_text())
    tree=[item for item in tree if not (isinstance(item,list) and str(item[0]) in ('segment','via','zone'))]
    temporary=ECAD/(spec.name+'_import.kicad_pcb');temporary.write_text(sexpdata.dumps(tree))
    board=pcb.LoadBoard(str(temporary));temporary.unlink()
    session=sexpdata.loads((ECAD/(spec.name+'.ses')).read_text())
    def child(node,tag):return next(x for x in node if isinstance(x,list) and str(x[0])==tag)
    routes=child(session,'routes');resolution=child(routes,'resolution')
    assert str(resolution[1])=='um'
    scale=1000*resolution[2]
    layers={'F.Cu':pcb.F_Cu,'B.Cu':pcb.B_Cu,'In1.Cu':pcb.In1_Cu,'In2.Cu':pcb.In2_Cu}
    for net in child(routes,'network_out')[1:]:
        netcode=board.FindNet(str(net[1])).GetNetCode()
        for item in net[2:]:
            if str(item[0])=='wire':
                route=child(item,'path');layer=layers[str(route[1])];width=route[2]/scale
                points=list(zip(route[3::2],route[4::2]))
                for a,b in zip(points,points[1:]):
                    track=pcb.PCB_TRACK(board);track.SetStart(vec(a[0]/scale,-a[1]/scale));track.SetEnd(vec(b[0]/scale,-b[1]/scale))
                    track.SetWidth(mm(width));track.SetLayer(layer);track.SetNetCode(netcode);board.Add(track)
            elif str(item[0])=='via':
                dims=re.search(r'_(\d+):(\d+)_um',str(item[1]));assert dims
                via=pcb.PCB_VIA(board);via.SetPosition(vec(item[2]/scale,-item[3]/scale));via.SetWidth(mm(int(dims[1])/1000));via.SetDrill(mm(int(dims[2])/1000))
                via.SetViaType(pcb.VIATYPE_THROUGH);via.SetLayerPair(pcb.F_Cu,pcb.B_Cu);via.SetNetCode(netcode);board.Add(via)
    gnd=board.FindNet('GND')
    for layer in ([pcb.F_Cu,pcb.B_Cu] if spec.layers==2 else [pcb.F_Cu,pcb.In1_Cu,pcb.In2_Cu,pcb.B_Cu]):
        zone=pcb.ZONE(board);zone.SetLayer(layer);zone.SetNetCode(gnd.GetNetCode())
        zone.SetLocalClearance(mm(.2));zone.SetPadConnection(pcb.ZONE_CONNECTION_FULL)
        zone.SetMinThickness(mm(.2));zone.SetThermalReliefGap(mm(.3));zone.SetThermalReliefSpokeWidth(mm(.3))
        poly=zone.Outline();poly.NewOutline()
        for x,y in [(.5,.5),(spec.width-.5,.5),(spec.width-.5,spec.height-.5),(.5,spec.height-.5)]:poly.Append(mm(x),mm(y))
        board.Add(zone)
    board.BuildConnectivity();pcb.ZONE_FILLER(board).Fill(board.Zones())
    pcb.SaveBoard(str(path),board)
    restore_rules(spec.name)

def restore_rules(name):
    project=ECAD/(name+'.kicad_pro');data=json.loads(project.read_text())
    for cls in data['net_settings']['classes']:
        if cls['name']=='Default':cls['clearance']=.15
    data['board']['design_settings']['rules'].update(min_clearance=.15,min_track_width=.15,
        min_via_diameter=.5,min_through_hole_diameter=.2,min_hole_clearance=.15)
    project.write_text(json.dumps(data,indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','finish']);parser.add_argument('names',nargs='*');args=parser.parse_args()
    for board in boards():
        if args.names and board.name not in args.names:continue
        prepare(board.name) if args.stage=='prepare' else finish(board)
        print(args.stage,board.name)
