"""Regenerate HF placement with explicit staggered fine-pitch escapes before routing."""
import pcbnew as pcb
from design import boards,write
from ecad import ECAD,mm,vec,vendor,schematic,pcb_board
from route import prepare,restore_rules

def main():
    spec=next(b for b in boards() if b.name=='hf');write();vendor(spec)
    pcb_board(spec,schematic(spec))
    path=ECAD/'hf.kicad_pcb';b=pcb.LoadBoard(str(path))
    for f in b.GetFootprints():
        if f.GetReference() not in ('U2','U3'):continue
        cx,cy=pcb.ToMM(f.GetPosition().x),pcb.ToMM(f.GetPosition().y)
        for p in f.Pads():
            if not p.GetNetname() or p.GetNumber()=='33':continue
            x,y=pcb.ToMM(p.GetPosition().x),pcb.ToMM(p.GetPosition().y)
            odd=int(p.GetNumber())%2
            if f.GetReference()=='U2':
                if abs(x-cx)>abs(y-cy):end=(cx+(4+odd)*(1 if x>cx else -1),y)
                else:end=(x,cy+(4+odd)*(1 if y>cy else -1))
            else:end=(cx+(4+odd)*(1 if x>cx else -1),y)
            t=pcb.PCB_TRACK(b);t.SetStart(p.GetPosition());t.SetEnd(vec(*end));t.SetWidth(mm(.15));t.SetLayer(pcb.F_Cu);t.SetNetCode(p.GetNetCode());b.Add(t)
            v=pcb.PCB_VIA(b);v.SetPosition(vec(*end));v.SetWidth(mm(.5));v.SetDrill(mm(.25));v.SetViaType(pcb.VIATYPE_THROUGH);v.SetLayerPair(pcb.F_Cu,pcb.B_Cu);v.SetNetCode(p.GetNetCode());b.Add(v)
    pcb.SaveBoard(str(path),b);restore_rules('hf');pcb.ExportSpecctraDSN(b,str(ECAD/'hf.dsn'));prepare('hf')

if __name__=='__main__':main()
