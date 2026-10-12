"""Generate editable KiCad files from explicit, reviewed pin-to-net mappings."""
import json
import math
import os
from pathlib import Path
import uuid
import shutil
import pcbnew as pcb
from design import OUT, boards, write

LIB=Path(os.environ.get('KICAD_FOOTPRINT_DIR',str(Path.home()/'.local/opt/skysentinel-cad/root/usr/share/kicad/footprints')))
ECAD=OUT/'ecad'
NS=uuid.UUID('ba4c2c69-4b88-4de4-8a0e-315f8b2f7fd2')
def uid(value): return str(uuid.uuid5(NS,value))
def q(s): return json.dumps(str(s))
def mm(v): return pcb.FromMM(v)
def vec(x,y): return pcb.VECTOR2I(mm(x),mm(y))

def custom_footprints():
    target=ECAD/'SkyWave.pretty';target.mkdir(parents=True,exist_ok=True)
    pads=[]
    for i in range(7):
        pads.append((str(i+1),13.35-i*4.45,9.5,2.2,3))
        pads.append((str(12+i),-13.35+i*4.45,-9.5,2.2,3))
    for i in range(4): pads.append((str(8+i),-17.8,6.9-i*4.6,3,2.2))
    for name,width,height,pad_data in [('DRA818',35.6,19,pads),('VLS3015ET',3,3,[('1',-1.2,0,1.2,2.8),('2',1.2,0,1.2,2.8)])]:
        lines=[f'(footprint "{name}" (version 20221018) (generator pcbnew) (layer "F.Cu") (attr smd)',
            f'(fp_text reference "REF**" (at 0 {-height/2-2}) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
            f'(fp_text value "{name}" (at 0 {height/2+2}) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))']
        for layer,extra in [('F.Fab',0),('F.CrtYd',1.7 if name=='DRA818' else .5)]:
            lines.append(f'(fp_rect (start {-width/2-extra} {-height/2-extra}) (end {width/2+extra} {height/2+extra}) (stroke (width 0.05) (type solid)) (fill none) (layer "{layer}"))')
        for n,x,y,sx,sy in pad_data:
            lines.append(f'(pad "{n}" smd rect (at {x} {y}) (size {sx} {sy}) (layers "F.Cu" "F.Paste" "F.Mask"))')
        (target/(name+'.kicad_mod')).write_text('\n'.join(lines)+')\n')

def pin_positions(part):
    entries=list(part['pins'].items());half=math.ceil(len(entries)/2)
    height=max(7.62,(half+1)*2.54);result=[]
    for i,(number,p) in enumerate(entries):
        right=i>=half;y=height/2-2.54-(i-half if right else i)*2.54
        result.append((number,p,17.78 if right else -17.78,y,180 if right else 0))
    return height,result

def symbol_definition(board,part,external=False):
    ident=board+'_'+part['ref'].replace('#','');name=ident if external else 'SkyWave:'+ident
    height,pins=pin_positions(part)
    lines=[f'(symbol {q(name)} (pin_names (offset 0.508)) (in_bom yes) (on_board yes)',
        f'(property "Reference" {q(part["ref"])} (at 0 {height/2+2.54} 0) (effects (font (size 1.27 1.27))))',
        f'(property "Value" {q(part["value"])} (at 0 {-height/2-2.54} 0) (effects (font (size 1 1))))',
        f'(symbol {q(ident+"_0_1")} (rectangle (start -15.24 {height/2}) (end 15.24 {-height/2}) (stroke (width 0.254) (type default)) (fill (type background))))',
        f'(symbol {q(ident+"_1_1")}']
    for number,p,x,y,angle in pins:
        lines.append(f'(pin {p["kind"]} line (at {x} {y} {angle}) (length 2.54) (name {q(p["name"])} (effects (font (size 0.9 0.9)))) (number {q(number)} (effects (font (size 0.9 0.9)))))')
    return '\n'.join(lines)+'))'

def schematic(board):
    root=uid(board.name+'/root');libs=[];instances=[]
    for i,part in enumerate(board.parts):
        libs.append(symbol_definition(board.name,part))
        h,pins=pin_positions(part);x=76.2+(i%8)*139.7;y=60.96+(i//8)*71.12
        symid=uid(board.name+'/'+part['ref']);part['uuid']=symid
        ident=board.name+'_'+part['ref'].replace('#','')
        prop=[('Reference',part['ref'],x,y-h/2-3,False),('Value',part['value'],x,y+h/2+3,False),
              ('Footprint',part['footprint'],x,y,True),('Datasheet',part['source'],x,y,True),('MPN',part['mpn'],x,y,True)]
        lines=[f'(symbol (lib_id {q("SkyWave:"+ident)}) (at {x} {y} 0) (unit 1) (in_bom {"no" if not part["footprint"] else "yes"}) (on_board {"no" if not part["footprint"] else "yes"}) (uuid {symid})']
        for key,value,px,py,hide in prop:
            lines.append(f'(property {q(key)} {q(value)} (at {px} {py} 0) (effects (font (size 1 1)) {"hide" if hide else ""}))')
        for number,p,px,py,a in pins: lines.append(f'(pin {q(number)} (uuid {uid(symid+"/"+number)}))')
        lines.append(f'(instances (project {q(board.name)} (path "/{root}" (reference {q(part["ref"])}) (unit 1))))')
        instances.append('\n'.join(lines)+')')
        for number,p,px,py,angle in pins:
            gx=x+px;gy=y-py
            if p['net'] is None:
                instances.append(f'(no_connect (at {gx} {gy}) (uuid {uid(symid+number+"nc")}))')
                continue
            end=gx+(5.08 if angle==180 else -5.08)
            instances.append(f'(wire (pts (xy {gx} {gy}) (xy {end} {gy})) (stroke (width 0) (type default)) (uuid {uid(symid+number+"wire")}))')
            a=0 if angle==180 else 180
            instances.append(f'(global_label {q(p["net"])} (shape bidirectional) (at {end} {gy} {a}) (effects (font (size 0.9 0.9)) (justify {"left" if angle==180 else "right"})) (uuid {uid(symid+number+"label")}))')
    text=f'(kicad_sch (version 20230121) (generator eeschema) (uuid {root}) (paper "A0") (title_block (title "SkyWave D1 - {board.name}") (date "2026-10-12") (rev "D1-prototype") (company "Daniel Marques / SkyWave SDR") (comment 1 "Engineering prototype - not production released"))\n(lib_symbols\n'+'\n'.join(libs)+')\n'+'\n'.join(instances)+'\n(sheet_instances (path "/" (page "1"))))\n'
    (ECAD/(board.name+'.kicad_sch')).write_text(text)
    return root

def body_box(foot):
    pts=[]
    for item in foot.GraphicalItems():
        if item.GetLayer()==pcb.F_Fab and isinstance(item,pcb.PCB_SHAPE):
            box=item.GetBoundingBox()
            pts += [(pcb.ToMM(box.GetX()),pcb.ToMM(box.GetY())),(pcb.ToMM(box.GetRight()),pcb.ToMM(box.GetBottom()))]
    if not pts:
        box=foot.GetBoundingBox(False,False)
        return [pcb.ToMM(box.GetX()),pcb.ToMM(box.GetY()),pcb.ToMM(box.GetWidth()),pcb.ToMM(box.GetHeight())]
    xs,ys=zip(*pts)
    return [min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)]

def pcb_board(board,root):
    result=pcb.BOARD();result.SetCopperLayerCount(board.layers)
    settings=result.GetDesignSettings();settings.SetBoardThickness(mm(1.6))
    settings.m_MinClearance=mm(.15);settings.m_TrackMinWidth=mm(.15)
    settings.m_ViasMinSize=mm(.6);settings.m_MinThroughDrill=mm(.2)
    netnames=sorted({p['net'] for c in board.parts for p in c['pins'].values() if p['net'] is not None})
    nets={}
    for i,name in enumerate(netnames,1):
        net=pcb.NETINFO_ITEM(result,name,i);result.Add(net);nets[name]=net
    metadata=[]
    for part in board.parts:
        if not part['footprint']:continue
        library,name=part['footprint'].split(':')
        path=ECAD/'SkyWave.pretty' if library=='SkyWave' else LIB/(library+'.pretty')
        foot=pcb.FootprintLoad(str(path),name)
        if foot is None:raise RuntimeError('Missing footprint: '+part['footprint'])
        foot.SetReference(part['ref']);foot.SetValue(part['value']);foot.SetFPID(pcb.LIB_ID(library,name))
        foot.SetPath(pcb.KIID_PATH('/'+root+'/'+part['uuid']))
        foot.SetPosition(vec(part['x'],part['y']));foot.SetOrientationDegrees(part['rotation'])
        used=set()
        for pad in foot.Pads():
            number=pad.GetNumber()
            if not number:continue
            if number not in part['pins']:raise ValueError(f'{board.name}/{part["ref"]}: footprint pad {number} not in circuit')
            used.add(number);net=part['pins'][number]['net']
            if net is not None:pad.SetNet(nets[net])
        missing=set(part['pins'])-used
        if missing:raise ValueError(f'{board.name}/{part["ref"]}: symbol pins absent from footprint: {missing}')
        foot.Reference().SetTextSize(vec(.8,.8));foot.Reference().SetTextThickness(mm(.12));foot.Value().SetVisible(False)
        result.Add(foot);metadata.append({**part,'body_bbox_mm':body_box(foot)})
    mounts=[(4,16),(116,4),(4,96),(116,96)] if board.name=='control' else [(4,4),(45,4),(4,45),(56,66)] if board.name in ('vhf','uhf') else [(44,4),(44,20)] if board.name.startswith('lpf') else [(4,4),(116,4),(4,96),(116,96)]
    for i,(x,y) in enumerate(mounts,1):
        hole=pcb.FootprintLoad(str(LIB/'MountingHole.pretty'),'MountingHole_3.2mm_M3')
        hole.SetReference('H'+str(i));hole.SetPosition(vec(x,y));hole.Reference().SetVisible(False);result.Add(hole)
    pts=[(0,0),(board.width,0),(board.width,board.height),(0,board.height)]
    for a,c in zip(pts,pts[1:]+pts[:1]):
        line=pcb.PCB_SHAPE();line.SetShape(pcb.SHAPE_T_SEGMENT);line.SetStart(vec(*a));line.SetEnd(vec(*c));line.SetLayer(pcb.Edge_Cuts);line.SetWidth(mm(.05));result.Add(line)
    label=pcb.PCB_TEXT(result);label.SetText('SKYWAVE '+board.name.upper()+' D1');label.SetPosition(vec(board.width/2,board.height-3));label.SetTextSize(vec(1,1));label.SetTextThickness(mm(.15));label.SetLayer(pcb.F_SilkS);result.Add(label)
    pcb.SaveBoard(str(ECAD/(board.name+'.kicad_pcb')),result)
    pcb.ExportSpecctraDSN(result,str(ECAD/(board.name+'.dsn')))
    (ECAD/(board.name+'_placement.json')).write_text(json.dumps(metadata,indent=2)+'\n')

def vendor(board):
    for part in board.parts:
        if not part["footprint"] or part["footprint"].startswith("SkyWave:"):continue
        lib,name=part["footprint"].split(":")
        local=lib+"_"+name
        shutil.copyfile(LIB/(lib+".pretty")/(name+".kicad_mod"),ECAD/"SkyWave.pretty"/(local+".kicad_mod"))
        if name=="MSOP-10_3x3mm_P0.5mm":
            fp=ECAD/"SkyWave.pretty"/(local+".kicad_mod")
            fp.write_text(fp.read_text().replace("  (clearance 0.2)\n",""))
        part["footprint"]="SkyWave:"+local

def main():
    write();ECAD.mkdir(parents=True,exist_ok=True);custom_footprints()
    libsymbols=[]
    for board in boards():
        vendor(board);root=schematic(board);pcb_board(board,root)
        libsymbols.extend(symbol_definition(board.name,p,True) for p in board.parts)
        project={'meta':{'filename':board.name+'.kicad_pro','version':1},'net_settings':{'classes':[{'name':'Default','clearance':.15,'track_width':.25,'via_diameter':.6,'via_drill':.3,'microvia_diameter':.3,'microvia_drill':.1,'diff_pair_width':.25,'diff_pair_gap':.2,'diff_pair_via_gap':.25}],'meta':{'version':3}},'board':{'design_settings':{'rules':{'min_clearance':.15,'min_track_width':.15,'min_via_diameter':.6,'min_through_hole_diameter':.2,'min_hole_clearance':.15}}}}
        (ECAD/(board.name+'.kicad_pro')).write_text(json.dumps(project,indent=2)+'\n')
        print('generated',board.name)
    (ECAD/'SkyWave.kicad_sym').write_text('(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n'+'\n'.join(libsymbols)+')\n')
    prefix=chr(36)+'{KIPRJMOD}'
    (ECAD/'sym-lib-table').write_text(f'(sym_lib_table (lib (name "SkyWave")(type "KiCad")(uri "{prefix}/SkyWave.kicad_sym")(options "")(descr "SkyWave symbols")))\n')
    (ECAD/'fp-lib-table').write_text(f'(fp_lib_table (lib (name "SkyWave")(type "KiCad")(uri "{prefix}/SkyWave.pretty")(options "")(descr "SkyWave custom footprints")))\n')

if __name__=='__main__':main()
