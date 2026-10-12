"""Independently read saved PCBs and compare every numbered pad to the circuit."""
import json
import pcbnew as pcb
from design import OUT,boards

results={}
for spec in boards():
    board=pcb.LoadBoard(str(OUT/'ecad'/(spec.name+'.kicad_pcb')))
    footprints={f.GetReference():f for f in board.GetFootprints()}
    count=0
    for part in spec.parts:
        if not part['footprint']:continue
        f=footprints[part['ref']]
        assert f.GetValue()==part['value'],(spec.name,part['ref'],'value')
        assert abs(pcb.ToMM(f.GetPosition().x)-part['x'])<.001
        assert abs(pcb.ToMM(f.GetPosition().y)-part['y'])<.001
        assert abs((f.GetOrientationDegrees()-part['rotation']+180)%360-180)<.001
        seen=set()
        for pad in f.Pads():
            if not pad.GetNumber():continue
            seen.add(pad.GetNumber());count+=1
            assert pad.GetNetname()==(part['pins'][pad.GetNumber()]['net'] or ''),(spec.name,part['ref'],pad.GetNumber(),pad.GetNetname())
        assert seen==set(part['pins']), (spec.name,part['ref'],'pad numbers')
    results[spec.name]={'pads_checked':count,'pins_nets_values_positions_passed':True}
(OUT/'reports/pcb_contracts.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
