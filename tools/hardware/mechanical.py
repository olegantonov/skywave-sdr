"""Parametric bench enclosure and honest component-envelope assemblies, in mm."""
import json
from pathlib import Path
import cadquery as cq
from design import OUT, boards

CAD=OUT/'cad'
W,D,H=164,120,74
WALL=2.5
MOUNTS={'control':[(4,16),(116,4),(4,96),(116,96)],
        'hf':[(4,4),(116,4),(4,96),(116,96)],
        'vhf':[(4,4),(45,4),(4,45),(56,66)],
        'uhf':[(4,4),(45,4),(4,45),(56,66)],
        'lpf40':[(44,4),(44,20)]}
PLACEMENT={'control':(8,10,50),'hf':(8,10,28),'vhf':(8,10,7),
           'uhf':(88,10,7),'lpf40':(83,86,7)}

def box(x,y,z,w,d,h):
    return cq.Workplane('XY').box(w,d,h,centered=False).translate((x,y,z))

def cylinder(x,y,z,r,h):return cq.Workplane('XY').circle(r).extrude(h).translate((x,y,z))

def export(obj,name):
    shape=obj.val() if isinstance(obj,cq.Workplane) else obj
    assert shape.isValid(),name
    cq.exporters.export(shape,str(CAD/(name+'.step')))
    cq.exporters.export(shape,str(CAD/(name+'.stl')),tolerance=.08,angularTolerance=.15)

def board_model(spec):
    pcb=box(0,0,0,spec.width,spec.height,1.6)
    for x,y in MOUNTS.get(spec.name,[(44,4),(44,20)]):
        pcb=pcb.cut(cylinder(x,y,-1,1.6,4))
    parts=json.loads((OUT/'ecad'/(spec.name+'_placement.json')).read_text())
    assembly=cq.Assembly(name=spec.name)
    assembly.add(pcb,name='laminate',color=cq.Color(.04,.29,.23))
    envelopes=[]
    for p in parts:
        x,y,w,d=p['body_bbox_mm'];h=p['height_mm']
        component=box(x,y,1.6,w,d,h)
        color=(.12,.13,.15) if p['ref'][0] in 'UQ' else (.72,.69,.58) if p['ref'][0]=='C' else (.55,.58,.62)
        assembly.add(component,name=p['ref'],color=cq.Color(*color))
        envelopes.append(dict(ref=p['ref'],bbox=[x,y,1.6,w,d,h],kind=p['geometry']))
    assembly.save(str(CAD/(spec.name+'_assembly.step')))
    export(pcb,spec.name+'_bare_board')
    return assembly,envelopes

def main():
    CAD.mkdir(exist_ok=True,parents=True)
    models={};bounds={}
    for spec in boards():models[spec.name],bounds[spec.name]=board_model(spec)
    base=box(0,0,0,W,D,H-3).cut(box(WALL,WALL,WALL,W-2*WALL,D-2*WALL,H))
    # USB service recess admits the plug housing to the PCB-mounted connector.
    base=base.cut(box(-1,55,48,15,24,14))
    base=base.cut(box(W-12,17,5,14,14,13))
    # Cable openings: panel PTT, regulated 5 V input and three SMA pigtails.
    for y,z,r in [(96,40,6),(98,59,4)]:
        hole=cq.Workplane('YZ').center(y,z).circle(r).extrude(W+2).translate((-1,0,0))
        base=base.cut(hole)
    for x in (32,73,114):
        hole=cq.Workplane('XZ').center(x,18).circle(3.3).extrude(5).translate((0,3,0))
        base=base.cut(hole)
    # Independent wall-supported ledges leave space for each removable board.
    for name,(dx,dy,z) in PLACEMENT.items():
        for x,y in MOUNTS[name]:
            px,py=x+dx,y+dy
            post=cylinder(px,py,z-3,3.5,3).cut(cylinder(px,py,z-4,1.2,5))
            if z==7:
                post=cylinder(px,py,WALL,3.5,z-WALL).cut(cylinder(px,py,WALL,1.2,z))
            else:
                left=px<W/2
                ledge=box(WALL if left else px,py-3.5,z-3,px-WALL if left else W-WALL-px,7,2)
                post=post.union(ledge)
            base=base.union(post)
    screws=[(4.5,4.5),(W-4.5,4.5),(4.5,D-4.5),(W-4.5,D-4.5)]
    for x,y in screws:
        base=base.union(cylinder(x,y,2,3.5,H-5)).cut(cylinder(x,y,H-14,1.2,15))
    lid=box(0,0,H-3,W,D,3)
    for x,y in screws:lid=lid.cut(cylinder(x,y,H-4,1.6,5))
    # Adjustable display tray: a dimensional envelope, not a certified module CAD.
    oled=(57,39,65,35.6,33.7,4)
    lid=lid.cut(box(59.5,47,H-4,30.6,17,6))
    tray=box(54,36,63,41.6,39.7,2).cut(box(56.8,38.8,62,36,34.1,4))
    for x in (55,94):
        tray=tray.union(box(x,36,63,1.5,39.7,8))
    lid=lid.union(tray)
    plungers=[]
    for i,(x,y) in enumerate([(77.25,88.25),(94.25,88.25),(111.25,88.25)]):
        lid=lid.cut(cylinder(x,y,H-4,3.25,6))
        cap=cylinder(x,y,56,2.8,19).union(cylinder(x,y,69.5,4,1))
        plungers.append(cap);export(cap.translate((-x,-y,-56)),'button_'+str(i+1))
    for x in range(20,46,5):lid=lid.cut(box(x,88,H-4,2,17,6))
    export(base,'enclosure_base');export(lid.translate((0,0,-(H-3))),'enclosure_lid')
    assembly=cq.Assembly(name='SkyWave_D1')
    assembly.add(base,name='base',color=cq.Color(.12,.16,.2,.35))
    assembly.add(lid,name='lid',color=cq.Color(.16,.21,.26,.45))
    for name,xyz in PLACEMENT.items():assembly.add(models[name],name=name,loc=cq.Location(cq.Vector(*xyz)))
    display=box(*oled);assembly.add(display,name='OLED_dimensional_envelope',color=cq.Color(.04,.07,.09))
    ptt=cq.Workplane('YZ').center(96,40).circle(5.5).extrude(12).translate((-3,0,0))
    assembly.add(ptt,name='PTT_panel_dimensional_envelope',color=cq.Color(.96,.49,.12))
    for i,cap in enumerate(plungers):assembly.add(cap,name='button_'+str(i),color=cq.Color(.96,.49,.12))
    assembly.save(str(CAD/'skywave_d1_assembly.step'))
    # Cross-board envelopes and enclosure shell, checked separately from supports.
    intersections=[]
    for name,xyz in PLACEMENT.items():
        for other,otherxyz in PLACEMENT.items():
            if name>=other:continue
            a=models[name].toCompound().moved(cq.Location(cq.Vector(*xyz)))
            b=models[other].toCompound().moved(cq.Location(cq.Vector(*otherxyz)))
            volume=a.intersect(b).Volume()
            if volume>1e-4:intersections.append(dict(a=name,b=other,volume_mm3=volume))
    shell_collisions=[]
    for name,xyz in PLACEMENT.items():
        model=models[name].toCompound().moved(cq.Location(cq.Vector(*xyz)))
        for label,shell in [('base',base),('lid',lid)]:
            volume=model.intersect(shell.val()).Volume()
            if volume>1e-3:shell_collisions.append(dict(board=name,shell=label,volume_mm3=volume))
    report={'units':'mm','enclosure_dimensions':[W,D,H],'pcb_placements':PLACEMENT,
        'board_to_enclosure_collisions':shell_collisions,
        'cross_board_collisions':intersections,'models_valid':True,
        'limits':['Component bodies are simplified envelopes; not manufacturer STEP models.',
        'OLED tray assumes 35.6 x 33.7 mm module; measure purchased module before printing.',
        'Cables, screws, speaker, microphone, panel PTT and SMA pigtails require assembly validation.',
        'No battery compartment or charging circuit. Bench enclosure, not Flipper-sized product.',
        '3D export and geometry checks do not validate print tolerances or heat dissipation.']}
    (OUT/'reports/mechanical.json').write_text(json.dumps(report,indent=2)+'\n')
    (CAD/'component_envelopes.json').write_text(json.dumps(bounds,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if intersections or shell_collisions:raise SystemExit('Mechanical collision')

if __name__=='__main__':main()
