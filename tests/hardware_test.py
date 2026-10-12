"""Check exported circuit artifacts and the physical inter-board pin contracts."""
from pathlib import Path
import json
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'hardware/d1'
BOARDS={b['name']:b for b in json.loads((DATA/'design.json').read_text())}

def part(board,ref):return next(p for p in BOARDS[board]['parts'] if p['ref']==ref)
def nets(board,ref):return {n:p['net'] for n,p in part(board,ref)['pins'].items()}

class HardwareContracts(unittest.TestCase):
    def test_exported_kicad_netlists_match_source(self):
        for name,board in BOARDS.items():
            root=ET.parse(DATA/'ecad'/(name+'.net')).getroot()
            actual={}
            for net in root.findall('./nets/net'):
                for node in net.findall('node'):
                    actual[(node.attrib['ref'],node.attrib['pin'])]=net.attrib['name'].lstrip('/')
            for p in board['parts']:
                if not p['footprint']:continue
                for n,pin in p['pins'].items():
                    if pin['net'] is not None:
                        self.assertEqual(actual.get((p['ref'],n)),pin['net'],(name,p['ref'],n))

    def test_connector_contracts(self):
        self.assertEqual(nets('control','J5'),nets('hf','J1'))
        for ctrl,module in [('J6','vhf'),('J7','uhf')]:
            mapping=nets('control',ctrl)
            expected={'1':'+5V','2':'GND','3':module.upper()+'_TX','4':module.upper()+'_RX',
                      '5':module.upper()+'_PTT_N','6':module.upper()+'_PD','7':module.upper()+'_MIC',
                      '8':module.upper()+'_AUDIO','9':'GND','10':'+3V3'}
            self.assertEqual(mapping,expected)
            self.assertEqual(nets(module,'J1'),{'1':'+5V','2':'GND','3':'UART_IN','4':'UART_OUT',
                '5':'PTT_N','6':'PD','7':'MIC','8':'AUDIO','9':'GND','10':'+3V3'})
        for name in ['lpf40','lpf20','lpf15','lpf10']:
            self.assertEqual(nets(name,'J1'),{'1':'RF_IN','2':'GND','3':'RF_OUT','4':'GND','5':'FILTER_ID','6':'GND'})

    def test_power_and_default_inhibit(self):
        self.assertEqual(nets('control','J3'),{'1':'+5V','2':'GND'})
        self.assertEqual(nets('control','U1')['31'],'TX_ARM')
        self.assertTrue(any(p['value']=='100k' and set(nets('control',p['ref']).values())=={'TX_ARM','GND'} for p in BOARDS['control']['parts']))
        for module in ['vhf','uhf']:
            self.assertEqual(nets(module,'U1')['7'],'GND')
            self.assertEqual(nets(module,'U1')['8'],'+4V')
        self.assertNotIn('+5V',nets('control','J4').values())

    def test_sources_and_artifacts(self):
        sources={s['id'] for s in json.loads((DATA/'sources.json').read_text())}
        for name,board in BOARDS.items():
            refs=[p['ref'] for p in board['parts']]
            self.assertEqual(len(refs),len(set(refs)))
            for p in board['parts']:
                if p['source']:self.assertIn(p['source'],sources)
            for suffix in ['.kicad_sch','.kicad_pcb','.kicad_pro']:
                self.assertTrue((DATA/'ecad'/(name+suffix)).is_file())
            self.assertTrue((DATA/'cad'/(name+'_assembly.step')).is_file())

if __name__=='__main__':unittest.main()
