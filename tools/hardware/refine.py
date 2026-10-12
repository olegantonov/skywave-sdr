"""Explicit board edits after routing; keep circuit/placement sources synchronized."""
import argparse
import json
import math
import sexpdata
import pcbnew as pcb
from ecad import ECAD, body_box, mm, vec
from route import restore_rules
from design import boards, write

def refine(spec):
    path=ECAD/(spec.name+'.kicad_pcb')
    if spec.name in ('vhf','uhf'):
        tree=sexpdata.loads(path.read_text())
        codes={x[1] for x in tree if isinstance(x,list) and str(x[0])=='net' and str(x[2]) in ('RF_FILTERED','PTT_N','GND')}
        def remove(x):
            return isinstance(x,list) and str(x[0]) in ('segment','via') and any(isinstance(y,list) and str(y[0])=='net' and y[1] in codes for y in x)
        seen=set();clean=[]
        for x in tree:
            if remove(x):continue
            if isinstance(x,list) and str(x[0])=='via':
                point=next(y for y in x if isinstance(y,list) and str(y[0])=='at')
                key=tuple(point[1:3])
                if key in seen:continue
                seen.add(key)
            clean.append(x)
        path.write_text('('+str(clean[0])+'\n'+'\n'.join(sexpdata.dumps(x) for x in clean[1:])+')\n')
    board=pcb.LoadBoard(str(path))
    if spec.name=="hf":
        for f in board.GetFootprints():
            if f.GetReference()=="U3":f.SetLocalClearance(0)
    def via_at(x,y,code):
        for v in board.GetTracks():
            if isinstance(v,pcb.PCB_VIA) and v.GetPosition()==vec(x,y):return
        via=pcb.PCB_VIA(board);via.SetPosition(vec(x,y));via.SetWidth(mm(.6));via.SetDrill(mm(.3))
        via.SetViaType(pcb.VIATYPE_THROUGH);via.SetLayerPair(pcb.F_Cu,pcb.B_Cu);via.SetNetCode(code);board.Add(via)
    def wire(points,net,layer=pcb.F_Cu,width=.2):
        code=board.FindNet(net).GetNetCode()
        for a,b in zip(points,points[1:]):
            t=pcb.PCB_TRACK(board);t.SetStart(vec(*a));t.SetEnd(vec(*b));t.SetWidth(mm(width));t.SetLayer(layer);t.SetNetCode(code);board.Add(t)
    if spec.name in ('hf','vhf','uhf'):
        ref='J3' if spec.name=='hf' else 'J2'
        foot=next(f for f in board.GetFootprints() if f.GetReference()==ref)
        foot.SetOrientationDegrees(0);foot.SetPosition(vec(spec.width-2.6,55 if spec.name=='hf' else 14))
        gnd=board.FindNet('GND').GetNetCode()
        for pad in foot.Pads():
            if pad.GetNumber()!='2':continue
            via_at(pcb.ToMM(pad.GetPosition().x),pcb.ToMM(pad.GetPosition().y),gnd)
    if spec.name in ('vhf','uhf'):
        code=board.FindNet('PTT_N').GetNetCode()
        via_at(18.175,62,code);via_at(19,55.5,code)
        wire([(20.8625,57),(19,57),(19,55.5)],'PTT_N')
        wire([(5,56.08),(3.5,56.08),(3.5,63.5),(18.175,63.5),(18.175,62),(19,61.175),(19,55.5)],'PTT_N',pcb.In2_Cu)
        wire([(41.5625,14),(43.3375,15.775),(53,15.775),(54.775,14),(57.4,14)],'RF_FILTERED',width=.35)
        # Stitch accessible ground regions while keeping every unrelated pad/trace clear.
        for x in range(3,58,5):
            for y in range(3,68,5):
                safe=True
                for f in board.GetFootprints():
                    for p in f.Pads():
                        if p.GetNetCode()==gnd:continue
                        bb=p.GetBoundingBox();bb.Inflate(mm(.55))
                        if bb.Contains(vec(x,y)):safe=False
                for t in board.GetTracks():
                    if t.GetNetCode()==gnd:continue
                    a=t.GetStart();b=t.GetEnd();ax,ay=pcb.ToMM(a.x),pcb.ToMM(a.y);bx,by=pcb.ToMM(b.x),pcb.ToMM(b.y)
                    dx,dy=bx-ax,by-ay;u=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
                    if math.hypot(x-ax-u*dx,y-ay-u*dy)<pcb.ToMM(t.GetWidth())/2+.5:safe=False
                if safe:via_at(x,y,gnd)
    for i in range(board.GetAreaCount()):board.GetArea(i).SetIslandRemovalMode(pcb.ISLAND_REMOVAL_MODE_ALWAYS)
    board.BuildConnectivity();pcb.ZONE_FILLER(board).Fill(board.Zones())
    if spec.name in ('vhf','uhf'):
        from matplotlib.path import Path
        for i in range(board.GetAreaCount()):
            zone=board.GetArea(i)
            if zone.GetLayer()!=pcb.F_Cu:continue
            polys=zone.GetFilledPolysList(pcb.F_Cu)
            for j in range(polys.OutlineCount()):
                outline=polys.Outline(j)
                points=[(pcb.ToMM(outline.CPoint(k).x),pcb.ToMM(outline.CPoint(k).y)) for k in range(outline.PointCount())]
                polygon=Path(points)
                if any(isinstance(v,pcb.PCB_VIA) and v.GetNetCode()==gnd and polygon.contains_point((pcb.ToMM(v.GetPosition().x),pcb.ToMM(v.GetPosition().y))) for v in board.GetTracks()):continue
                bb=outline.BBox();placed=False
                for ix in range(int(pcb.ToMM(bb.GetX())*4),int(pcb.ToMM(bb.GetRight())*4)+1):
                    for iy in range(int(pcb.ToMM(bb.GetY())*4),int(pcb.ToMM(bb.GetBottom())*4)+1):
                        x,y=ix/4,iy/4
                        if not all(polygon.contains_point((x+.35*math.cos(a),y+.35*math.sin(a))) for a in [k*math.pi/4 for k in range(8)]):continue
                        safe=True
                        for f in board.GetFootprints():
                            for p in f.Pads():
                                if p.GetNetCode()==gnd:continue
                                rect=p.GetBoundingBox();rect.Inflate(mm(.55))
                                if rect.Contains(vec(x,y)):safe=False
                        for t in board.GetTracks():
                            if t.GetNetCode()==gnd:continue
                            a=t.GetStart();b=t.GetEnd();ax,ay=pcb.ToMM(a.x),pcb.ToMM(a.y);dx,dy=pcb.ToMM(b.x)-ax,pcb.ToMM(b.y)-ay
                            u=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
                            if math.hypot(x-ax-u*dx,y-ay-u*dy)<pcb.ToMM(t.GetWidth())/2+.5:safe=False
                        if safe:via_at(x,y,gnd);placed=True;break
                    if placed:break
                if not placed:print('Unstitched polygon',spec.name,j)
        board.BuildConnectivity();pcb.ZONE_FILLER(board).Fill(board.Zones())
    pcb.SaveBoard(str(path),board);restore_rules(spec.name)
    if spec.name in ('hf','vhf','uhf'):
        ref='J3' if spec.name=='hf' else 'J2'
        pro=ECAD/(spec.name+'.kicad_pro');data=json.loads(pro.read_text())
        data['board']['design_settings']['rules']['min_copper_edge_clearance']=0
        pro.write_text(json.dumps(data,indent=2)+'\n')
        (ECAD/(spec.name+'.kicad_dru')).write_text('(version 1)\n(rule "Normal copper edge" (constraint edge_clearance (min 0.5mm)))\n(rule "SMA edge launch pads intentionally reach board edge" (condition "A.memberOfFootprint(\''+ref+'\')") (constraint edge_clearance (min 0mm)))\n')
    metadata=[]
    byref={p['ref']:p for p in spec.parts}
    for f in board.GetFootprints():
        if f.GetReference() in byref:metadata.append({**byref[f.GetReference()],'body_bbox_mm':body_box(f)})
    (ECAD/(spec.name+'_placement.json')).write_text(json.dumps(metadata,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('names',nargs='*');args=p.parse_args()
    write()
    for b in boards():
        if not args.names or b.name in args.names:refine(b);print('refined',b.name)
