"""D1 circuit source; pin numbers follow the references in sources.json."""
from pathlib import Path
import csv
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'hardware/d1'
SO8 = 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'
SO14 = 'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm'
SO16 = 'Package_SO:SOIC-16_3.9x9.9mm_P1.27mm'
SOT5 = 'Package_TO_SOT_SMD:SOT-23-5'
RFP = 'Resistor_SMD:R_0603_1608Metric'
CFP = 'Capacitor_SMD:C_0603_1608Metric'
HF_HEADER = ['+5V','GND','+3V3','GND','I2C_SDA','I2C_SCL','I2S_MCLK','I2S_BCLK','I2S_LRCK','I2S_TX','I2S_RX','CODEC_RESET_N','HF_TX_N','HF_AUDIO','HF_MIC','GND','FILTER_ID','LO_RESET_N','GND','GND']
HT_HEADER = ['+5V','GND','UART_IN','UART_OUT','PTT_N','PD','MIC','AUDIO','GND','+3V3']

def pin(name, net, kind='passive'):
    return dict(name=name, net=net, kind=kind)

class Board:
    def __init__(self,name,width,height,layers=2):
        self.name,self.width,self.height,self.layers=name,width,height,layers
        self.parts=[]; self.counts={}; self.filters=[]; self.notes=[]

    def add(self,prefix,value,footprint,nets,xy,source='',height=1.5,angle=0,mpn=None):
        self.counts[prefix]=self.counts.get(prefix,0)+1
        ref=f'{prefix}{self.counts[prefix]}'
        pins={str(k):(v if isinstance(v,dict) else pin(str(k),v)) for k,v in nets.items()}
        self.parts.append(dict(ref=ref,value=value,mpn=mpn or value,footprint=footprint,
            pins=pins,x=xy[0],y=xy[1],rotation=angle,height_mm=height,source=source,
            geometry='KiCad footprint / simplified body envelope'))
        return ref

    def r(self,value,a,b,x,y,angle=0):
        return self.add('R',value,RFP,{1:a,2:b},(x,y),'vishay_resistors',.5,angle,
                        'CRCW0603 series; value='+value+'; 1%')

    def c(self,value,a,b,x,y,angle=0):
        size='0805' if value in ('10u','22u') else '0603'
        fp='Capacitor_SMD:C_0805_2012Metric' if size=='0805' else CFP
        dielectric='C0G' if value.endswith('p') or value in ('1n','10n') else 'X7R'
        return self.add('C',value,fp,{1:a,2:b},(x,y),'kemet_capacitors',1,angle,
            f'KEMET {size} {dielectric} 25V; {value}; 5% RF/10% decoupling')

    def header(self,name,nets,xy,rows=1,angle=0):
        fp=f'Connector_PinHeader_2.54mm:PinHeader_{rows}x{len(nets)//rows:02d}_P2.54mm_Vertical'
        return self.add('J',name,fp,{i+1:n for i,n in enumerate(nets)},xy,'samtec_headers',8.5,angle,
            f'Samtec TSW-{len(nets)//rows:03d}-07-{"D" if rows==2 else "S"}-S')

    def power_flag(self,net):
        self.add('#FLG',net,'',{1:pin('pwr',net,'power_out')},(0,0),height=0)

def supply_pins(mapping,power=(),outputs=(),inputs=()):
    return {n:pin(name,net,'power_in' if n in power else 'output' if n in outputs else 'input' if n in inputs else 'passive') for n,(name,net) in mapping.items()}

def main_board():
    b=Board('control',120,100)
    gpio={4:'PTT_BUTTON_N',5:'BTN_DOWN',6:'BTN_UP',7:'BTN_BAND',15:'CODEC_RESET_N',16:'VHF_RX',17:'VHF_TX',18:'UHF_RX',8:'I2C_SDA',19:'USB_DM',20:'USB_DP',9:'I2C_SCL',10:'I2S_MCLK',11:'I2S_BCLK',12:'I2S_LRCK',13:'I2S_TX',14:'I2S_RX',21:'UHF_TX',48:'LO_RESET_N',38:'TX_ARM',39:'MODULE_A',40:'MODULE_B',41:'VHF_PD',42:'UHF_PD',1:'FILTER_ID'}
    gpio_pads={4:4,5:5,6:6,7:7,15:8,16:9,17:10,18:11,8:12,19:13,20:14,3:15,46:16,9:17,10:18,11:19,12:20,13:21,14:22,21:23,47:24,48:25,45:26,0:27,35:28,36:29,37:30,38:31,39:32,40:33,41:34,42:35,44:36,43:37,2:38,1:39}
    p={1:pin('GND','GND','power_in'),2:pin('3V3','+3V3','power_in'),3:pin('EN','ESP_EN','input'),40:pin('GND','GND','power_in'),41:pin('EP','GND','power_in')}
    for g,n in gpio_pads.items(): p[n]=pin(f'IO{g}',gpio.get(g,'BOOT_N' if g==0 else None),'bidirectional')
    b.add('U','ESP32-S3-WROOM-1-N8','RF_Module:ESP32-S3-WROOM-1',p,(27,18),'esp32',3.25)
    b.r('10k','+3V3','ESP_EN',14,36); b.c('1u','ESP_EN','GND',14,39)
    b.r('10k','+3V3','BOOT_N',20,36)
    for i,(signal,x) in enumerate([('ESP_EN',13),('BOOT_N',26),('BTN_DOWN',66),('BTN_UP',83),('BTN_BAND',100)]):
        b.add('SW','B3F-1000','Button_Switch_THT:SW_PUSH_6mm',{1:signal,2:'GND'},(x,76 if i>1 else 50),'buttons',4.3)
    for i,signal in enumerate(['PTT_BUTTON_N','BTN_DOWN','BTN_UP','BTN_BAND']): b.r('10k',signal,'+3V3',61+i*9,88)
    b.header('PTT_PANEL',['PTT_BUTTON_N','GND'],(113,76))
    b.header('OLED_I2C',['GND','+3V3','I2C_SCL','I2C_SDA'],(72,24))
    b.r('4.7k','I2C_SDA','+3V3',77,35); b.r('4.7k','I2C_SCL','+3V3',85,35)
    b.r('10k','FILTER_ID','+3V3',48,42); b.c('100n','FILTER_ID','GND',48,45)
    b.header('POWER_5V',['+5V','GND'],(107,92))
    b.add('U','LM1117IMP-3.3','Package_TO_SOT_SMD:SOT-223',{1:pin('GND','GND','power_in'),2:pin('OUT','+3V3','power_out'),3:pin('IN','+5V','power_in'),4:pin('TAB','+3V3','passive')},(96,55),'ldo',1.8)
    b.c('10u','+5V','GND',103,55); b.c('100n','+5V','GND',103,59)
    b.add('C','22u tantalum','Capacitor_Tantalum_SMD:CP_EIA-3528-21_Kemet-B',{1:'+3V3',2:'LDO_ESR'},(87,55),'tantalum',2.1,mpn='T491B226K016AT')
    b.r('0.47','LDO_ESR','GND',85,59)
    b.c('10u','+3V3','GND',12,29); b.c('100n','+3V3','GND',12,32)
    usb={k:pin(k,'GND' if k in ['A1','A12','B1','B12','S1'] else 'VBUS_USB' if k in ['A4','A9','B4','B9'] else 'USB_DP_CONN' if k in ['A6','B6'] else 'USB_DM_CONN' if k in ['A7','B7'] else 'CC1' if k=='A5' else 'CC2' if k=='B5' else None)
         for k in ['A1','A4','A5','A6','A7','A8','A9','A12','B1','B4','B5','B6','B7','B8','B9','B12','S1']}
    b.add('J','USB4105-GF-A','Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',usb,(4,56),'usb',3.3,90)
    b.r('5.1k','CC1','GND',11,59); b.r('5.1k','CC2','GND',11,63)
    b.r('22','USB_DM_CONN','USB_DM',16,57); b.r('22','USB_DP_CONN','USB_DP',16,60)
    b.c('100n','VBUS_USB','GND',11,67)
    b.add('U','USBLC6-2SC6','Package_TO_SOT_SMD:SOT-23-6',{1:'USB_DP_CONN',2:'GND',3:'USB_DM_CONN',4:'USB_DM_CONN',5:'VBUS_USB',6:'USB_DP_CONN'},(11,54),'esd',1.1)
    b.add('U','SN74LVC1G04DBVR',SOT5,{1:None,2:pin('A','PTT_BUTTON_N','input'),3:'GND',4:pin('Y','PTT_PRESSED','output'),5:'+3V3'},(53,52),'inverter',1.45)
    b.add('U','SN74LVC1G00DBVR',SOT5,{1:pin('A','PTT_PRESSED','input'),2:pin('B','TX_ARM','input'),3:'GND',4:pin('Y','TX_ENABLE_N','output'),5:'+3V3'},(62,52),'nand',1.45)
    b.r('100k','TX_ARM','GND',56,59)
    b.add('U','SN74HC139D',SO16,{1:pin('1G','TX_ENABLE_N','input'),2:pin('1A','MODULE_A','input'),3:pin('1B','MODULE_B','input'),4:pin('1Y0','HF_TX_N','output'),5:pin('1Y1','VHF_PTT_N','output'),6:pin('1Y2','UHF_PTT_N','output'),7:None,8:'GND',9:None,10:None,11:None,12:None,13:'GND',14:'GND',15:'+3V3',16:'+3V3'},(73,53),'decoder',1.75)
    b.r('100k','MODULE_A','+3V3',65,63); b.r('100k','MODULE_B','+3V3',74,63)
    b.header('HF_INTERFACE',HF_HEADER,(55,10),2)
    for prefix,x in [('VHF',20),('UHF',40)]:
        nets=['+5V','GND',f'{prefix}_TX',f'{prefix}_RX',f'{prefix}_PTT_N',f'{prefix}_PD',f'{prefix}_MIC',f'{prefix}_AUDIO','GND','+3V3']
        b.header(prefix+'_INTERFACE',nets,(x,70),2); b.r('100k',prefix+'_PD','GND',x,88)
    b.add('U','CD74HCT4052M',SO16,{1:'HF_AUDIO_B',2:'UHF_AUDIO_B',3:'AUDIO_SELECTED',4:'VMID',5:'VHF_AUDIO_B',6:'GND',7:'GND',8:'GND',9:'MODULE_B',10:'MODULE_A',11:'VMID',12:'HF_MIC_B',13:'MIC_B',14:'VHF_MIC_B',15:'UHF_MIC_B',16:'+5V'},(85,43),'audio_mux',1.75)
    b.r('10k','+5V','VMID',102,40); b.r('10k','VMID','GND',109,40); b.c('10u','VMID','GND',109,44)
    for i,name in enumerate(['HF','VHF','UHF']):
        x=58+i*12
        b.c('1u',name+'_AUDIO',name+'_AUDIO_B',x,39); b.r('100k',name+'_AUDIO_B','VMID',x,42)
        b.c('1u',name+'_MIC_B',name+'_MIC',x,46); b.r('100k',name+'_MIC_B','VMID',x,49)
    b.header('MIC_ELECTRET',['MIC_RAW','GND'],(105,14))
    b.r('2.2k','+3V3','MIC_RAW',98,15); b.c('1u','MIC_RAW','MIC_B',98,20); b.r('100k','MIC_B','VMID',105,23)
    b.c('1u','AUDIO_SELECTED','VOL_TOP',95,66)
    b.add('RV','10k volume','Potentiometer_THT:Potentiometer_Bourns_3296W_Vertical',{1:'GND',2:'AMP_IN',3:'VOL_TOP'},(105,69),'volume',10,mpn='3296W-1-103LF')
    b.add('U','LM386N-1','Package_DIP:DIP-8_W7.62mm',{1:None,2:'GND',3:pin('IN','AMP_IN','input'),4:'GND',5:pin('OUT','AMP_OUT','output'),6:'+5V',7:'AMP_BYPASS',8:None},(85,70),'audio_amp',5)
    b.c('10u','AMP_BYPASS','GND',78,73); b.c('100n','+5V','GND',92,72)
    b.c('100n','AMP_OUT','ZOBEL',84,83); b.r('10','ZOBEL','GND',89,83)
    b.add('C','220u','Capacitor_THT:CP_Radial_D6.3mm_P2.50mm',{1:'AMP_OUT',2:'SPEAKER'},(96,82),'electrolytic',11.2,mpn='EEUFR1A221')
    b.header('SPEAKER_8_OHM',['SPEAKER','GND'],(100,91))
    for i,(x,y) in enumerate([(49,55),(63,56),(78,56),(89,39)]): b.c('100n','+3V3' if i<3 else '+5V','GND',x,y)
    for net in ['+5V','GND','VBUS_USB']: b.power_flag(net)
    b.notes+=['USB data-only; regulated external 5 V / 2 A supply required.', 'Physical PTT AND TX_ARM gates a one-of-three decoder.', 'Driver implementation and physical validation pending.']
    return b

def hf_board():
    b=Board('hf',120,100,4)
    b.header('CONTROL_INTERFACE',HF_HEADER,(10,10),2)
    b.add('U','TLV75518PDBVR',SOT5,{1:'+3V3',2:'GND',3:'+3V3',4:None,5:pin('OUT','+1V8','power_out')},(20,37),'ldo18',1.45)
    b.c('1u','+3V3','GND',16,37); b.c('1u','+1V8','GND',25,37)
    codec={1:('MCLK','I2S_MCLK'),2:('BCLK','I2S_BCLK'),3:('WCLK','I2S_LRCK'),4:('DIN','I2S_TX'),5:('DOUT','I2S_RX'),6:('IOVDD','+3V3'),7:('IOVSS','GND'),8:('MFP3','GND'),9:('SCL','I2C_SCL'),10:('SDA','I2C_SDA'),11:('MFP4',None),12:('SPI_SEL','GND'),13:('IN1L','ADC_I'),14:('IN1R','ADC_Q'),15:('IN2L','MIC_IN'),16:('IN2R',None),17:('AVSS','GND'),18:('REF','CODEC_REF'),19:('MICBIAS',None),20:('IN3L',None),21:('IN3R',None),22:('LOL','DAC_I'),23:('LOR','DAC_Q'),24:('AVDD','+1V8'),25:('HPL','AUDIO_RAW'),26:('LDOIN','+3V3'),27:('HPR',None),28:('DVSS','GND'),29:('DVDD','+1V8'),30:('LDO_SEL','GND'),31:('RESET','CODEC_RESET_N'),32:('GPIO',None),33:('EP','GND')}
    b.add('U','TLV320AIC3204IRHBR','Package_DFN_QFN:Texas_RHB0032E_VQFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm',supply_pins(codec,(6,7,17,24,26,28,29,33),(5,18,22,23,25,27),(1,4,8,9,12,30,31)),(28,27),'codec',1)
    for i,rail in enumerate(['+3V3','+1V8','+1V8','+3V3']): b.c('100n',rail,'GND',23+i*3,33)
    b.c('10u','CODEC_REF','GND',34,27); b.c('1u','AUDIO_RAW','HF_AUDIO',35,20); b.c('1u','HF_MIC','MIC_IN',35,23)
    b.r('10k','CODEC_RESET_N','GND',22,20)
    b.add('U','SI5351A-B-GT','Package_SO:MSOP-10_3x3mm_P0.5mm',{1:'+3V3',2:'XTAL_A',3:'XTAL_B',4:pin('SCL','I2C_SCL','input'),5:pin('SDA','I2C_SDA','bidirectional'),6:None,7:'+3V3',8:'GND',9:None,10:pin('CLK0','LO4_RAW','output')},(63,18),'si5351',1.1)
    b.add('Y','25MHz 10pF','Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',{1:'XTAL_A',2:'GND',3:'XTAL_B',4:'GND'},(60,11),'crystal',.8,mpn='Abracon ABM8-25.000MHZ-10-1-U-T')
    b.c('100n','+3V3','GND',68,17); b.r('33','LO4_RAW','LO4',70,20)
    b.add('U','74LVC74APW','Package_SO:TSSOP-14_4.4x5mm_P0.65mm',{1:'LO_RESET_N',2:'LO_Q_N',3:'LO4',4:'+3V3',5:pin('1Q','LO_I','output'),6:None,7:'GND',8:pin('2Q_N','LO_Q_N','output'),9:pin('2Q','LO_Q','output'),10:'+3V3',11:'LO4',12:'LO_I',13:'LO_RESET_N',14:'+3V3'},(81,18),'flipflop',1.1)
    b.r('10k','LO_RESET_N','GND',85,12); b.c('100n','+3V3','GND',86,20)
    b.add('U','SN74LVC1G04DBVR',SOT5,{1:None,2:'HF_TX_N',3:'GND',4:pin('Y','HF_TX','output'),5:'+3V3'},(103,75),'inverter',1.45)
    b.r('10k','HF_TX_N','+3V3',109,74)
    b.r('10k','+5V','VMID_RAW',45,24); b.r('10k','VMID_RAW','GND',49,24); b.c('10u','VMID_RAW','GND',48,28)
    rxamp={1:pin('OUT1','RX_I','output'),2:'RX_I_NEG',3:'RX_I_POS',4:'+5V',5:'RX_Q_POS',6:'RX_Q_NEG',7:pin('OUT2','RX_Q','output'),8:pin('OUT3','VMID','output'),9:'VMID',10:'VMID_RAW',11:'GND',12:'VMID',13:'SPARE_OUT',14:pin('OUT4','SPARE_OUT','output')}
    b.add('U','TLV9064IDR',SO14,rxamp,(45,43),'opamp',1.75)
    for i,ch in enumerate(['I','Q']):
        y=35+i*18
        b.r('10k','DET_'+ch+'P','RX_'+ch+'_POS',57,y)
        b.r('100k','RX_'+ch+'_POS','VMID',52,y); b.c('100p','RX_'+ch+'_POS','VMID',52,y+3)
        b.r('10k','DET_'+ch+'N','RX_'+ch+'_NEG',57,y+6)
        b.r('100k','RX_'+ch+'_NEG','RX_'+ch,52,y+6); b.c('100p','RX_'+ch+'_NEG','RX_'+ch,52,y+9)
        b.r('1k','RX_'+ch,'LP_'+ch,36,y+6); b.c('10n','LP_'+ch,'GND',31,y+6)
        b.c('1u','LP_'+ch,'ADC_'+ch,27,y+6)
    b.c('100n','+5V','GND',40,40)
    txamp={1:pin('OUT1','TX_IP','output'),2:'TX_IP',3:'TX_I_BIAS',4:'+5V',5:'VMID',6:'TX_I_INV',7:pin('OUT2','TX_IN','output'),8:pin('OUT3','TX_QP','output'),9:'TX_QP',10:'TX_Q_BIAS',11:'GND',12:'VMID',13:'TX_Q_INV',14:pin('OUT4','TX_QN','output')}
    b.add('U','TLV9064IDR',SO14,txamp,(45,76),'opamp',1.75)
    for i,ch in enumerate(['I','Q']):
        y=65+i*22
        b.c('1u','DAC_'+ch,'TX_'+ch+'_BIAS',28,y); b.r('100k','TX_'+ch+'_BIAS','VMID',34,y)
        b.r('10k','TX_'+ch+'P','TX_'+ch+'_INV',54,y); b.r('10k','TX_'+ch+'_INV','TX_'+ch+'N',54,y+4)
        for j,phase in enumerate(['P','N']):
            b.r('100','TX_'+ch+phase,'TX_'+ch+phase+'_F',61+j*6,y)
            b.c('10n','TX_'+ch+phase+'_F','VMID',61+j*6,y+4)
    b.c('100n','+5V','GND',39,76)
    for kind,y,oe,common,phases in [('RX',43,'HF_TX','MIX_RX',['DET_IP','DET_QP','DET_QN','DET_IN']),('TX',70,'HF_TX_N','MIX_TX',['TX_IP_F','TX_QP_F','TX_QN_F','TX_IN_F'])]:
        p={1:oe,2:'LO_Q',3:phases[3],4:phases[2],5:phases[1],6:phases[0],7:common,8:'GND',9:common,10:phases[0],11:phases[1],12:phases[2],13:phases[3],14:'LO_I',15:oe,16:'+5V'}
        b.add('U','SN74CBT3253DR',SO16,p,(82,y),'mixer',1.75); b.c('100n','+5V','GND',89,y)
    for i,phase in enumerate(['IP','QP','QN','IN']): b.c('10n','DET_'+phase,'VMID',68+(i%2)*6,34+(i//2)*5)
    b.c('100n','RF_RX','MIX_RX',94,46); b.r('49.9','MIX_RX','VMID',93,42)
    b.c('100n','MIX_TX','TX_AC',94,66); b.r('49.9','TX_AC','RF_TX',99,66)
    b.add('K','G6K-2F-Y-DC5','Relay_SMD:Relay_DPDT_Omron_G6K-2F-Y',{1:'+5V',2:'RF_RX',3:'RF_COMMON',4:'RF_TX',5:None,6:None,7:None,8:'COIL_LOW'},(105,55),'relay',5.2)
    b.add('Q','2N7002','Package_TO_SOT_SMD:SOT-23',{1:'HF_TX',2:'GND',3:'COIL_LOW'},(109,65),'mosfet',1.1)
    b.add('D','1N4148W','Diode_SMD:D_SOD-123',{1:'+5V',2:'COIL_LOW'},(110,61),'diode',1.2)
    b.r('100k','HF_TX','GND',114,68)
    b.header('FILTER_CARTRIDGE',['RF_COMMON','GND','ANT_HF','GND','FILTER_ID','GND'],(102,87),2)
    b.add('J','SMA 132289','Connector_Coaxial:SMA_Amphenol_132289_EdgeMount',{1:'ANT_HF',2:'GND'},(117.4,55),'sma',8,0,mpn='Amphenol 132289')
    b.c('10u','+5V','GND',17,10); b.c('10u','+3V3','GND',17,14)
    for net in ['+5V','+3V3','GND']: b.power_flag(net)
    b.notes+=['HF TX is a low-level exciter; no RF PA fitted.', 'Install matching 50-ohm LPF cartridge before RX/TX.', 'Four-times LO tops at 118.8 MHz; timing margin requires bench confirmation.']
    return b

def ht_board(name):
    b=Board(name,60,70,4)
    b.header('CONTROL_INTERFACE',HT_HEADER,(5,51),2)
    p={1:pin('SQ',None,'output'),2:None,3:pin('AF_OUT','AUDIO_RAW','output'),4:None,5:pin('PTT','DRA_PTT_N','input'),6:pin('PD','PD','input'),7:'GND',8:pin('VBAT','+4V','power_in'),9:'GND',10:'GND',11:None,12:'RF_RAW',13:None,14:None,15:None,16:pin('RXD','UART_IN_R','input'),17:pin('TXD','UART_OUT_RAW','output'),18:'MIC_IN'}
    b.add('U','DRA818V' if name=='vhf' else 'DRA818U','SkyWave:DRA818',p,(30,37),name,6)
    b.add('U','TPS62160DGKR','Package_SO:VSSOP-8_3.0x3.0mm_P0.65mm',{1:'GND',2:'+5V',3:'+5V',4:'GND',5:'BUCK_FB',6:'+4V',7:pin('SW','BUCK_SW','output'),8:None},(40,59),'buck',1.1)
    b.add('L','2.2u','SkyWave:VLS3015ET',{1:'BUCK_SW',2:'+4V'},(46,59),'power_inductor',1.5,mpn='VLS3015ET-2R2M')
    b.c('10u','+5V','GND',35,59); b.c('22u','+4V','GND',47,64)
    b.r('402k','+4V','BUCK_FB',39,65); b.r('100k','BUCK_FB','GND',35,65)
    b.c('100n','+4V','GND',13,43); b.c('22u','+4V','GND',13,47)
    b.r('1k','UART_IN','UART_IN_R',49,43)
    b.add('U','SN74LVC1G17DBVR',SOT5,{1:None,2:'UART_OUT_RAW',3:'GND',4:pin('Y','UART_OUT','output'),5:'+3V3'},(50,51),'uart_buffer',1.45)
    b.add('U','SN74LVC1G04DBVR',SOT5,{1:None,2:'PTT_N',3:'GND',4:pin('Y','PTT_GATE','output'),5:'+3V3'},(22,57),'inverter',1.45)
    b.add('Q','2N7002','Package_TO_SOT_SMD:SOT-23',{1:'PTT_GATE',2:'GND',3:'DRA_PTT_N'},(26,51),'mosfet',1.1)
    b.r('10k','DRA_PTT_N','+4V',23,47); b.r('100k','PTT_GATE','GND',30,53)
    b.r('100k','PD','GND',17,53); b.r('10k','PTT_N','+3V3',19,62)
    b.c('100n','+3V3','GND',47,54); b.c('100n','+3V3','GND',23,61)
    b.c('1u','MIC','MIC_IN',49,25); b.c('1u','AUDIO_RAW','AUDIO',47,47)
    vals=([7.5,30,30,7.5],[47,82,47]) if name=='vhf' else ([2.4,10,10,2.4],[18,27,18])
    nodes=['RF_RAW','LP1','LP2','RF_FILTERED']
    for i in range(4):
        b.c(str(vals[0][i])+'p',nodes[i],'GND',18+i*9,15,90)
        if i<3: b.add('L',str(vals[1][i])+'n','Inductor_SMD:L_0805_2012Metric',{1:nodes[i],2:nodes[i+1]},(22.5+i*9,14),'rf_inductor',1.3,mpn='0805CS-'+str(vals[1][i]*10).zfill(3)+'XJRC')
    b.add('J','SMA 132289','Connector_Coaxial:SMA_Amphenol_132289_EdgeMount',{1:'RF_FILTERED',2:'GND'},(57.4,14),'sma',8,0,mpn='Amphenol 132289')
    b.filters.append(dict(name=name,c_pf=vals[0],l_nh=vals[1],passband_hz=[144e6,148e6] if name=='vhf' else [430e6,440e6]))
    for net in ['+5V','+3V3','+4V','GND']: b.power_flag(net)
    b.notes+=['H/L grounded: nominal 0.5 W; not measured.', 'DRA land pattern derived from bottom view and checked against top-view pin numbering.', 'DRA thickness: unverified 6 mm clearance envelope.']
    return b

def filter_board(name,c,l,resistor):
    b=Board(name,48,24,4)
    b.header('HF_FILTER',['RF_IN','GND','RF_OUT','GND','FILTER_ID','GND'],(4,7),2)
    nodes=['RF_IN','LP1','LP2','RF_OUT']
    for i in range(4):
        b.c(str(c[i])+'p',nodes[i],'GND',13+i*9,11,90)
        if i<3: b.add('L',str(l[i])+'n','Inductor_SMD:L_0805_2012Metric',{1:nodes[i],2:nodes[i+1]},(17.5+i*9,10),'rf_inductor',1.3,mpn='0805CS-'+str(l[i])[:2]+str(len(str(l[i]))-2)+'XJRC')
    b.r(resistor,'FILTER_ID','GND',16,19); b.power_flag('GND')
    b.filters.append(dict(name=name,c_pf=c,l_nh=l,passband_hz={'lpf40':[7e6,7.3e6],'lpf20':[14e6,14.35e6],'lpf15':[21e6,21.45e6],'lpf10':[28e6,29.7e6]}[name]))
    return b

def boards():
    result = [main_board(),hf_board(),ht_board('vhf'),ht_board('uhf'),
        filter_board('lpf40',[150,620,620,150],[1200,1800,1200],'1k'),
        filter_board('lpf20',[75,300,300,75],[560,1000,560],'2.2k'),
        filter_board('lpf15',[51,200,200,51],[390,680,390],'4.7k'),
        filter_board('lpf10',[36,150,150,36],[270,470,270],'10k')]
    positions = {
        'control': {'SW1':(25,42),'U7':(97,33),'U8':(50,67),'RV1':(67,67),'C18':(43,67),'C19':(59,63),'C20':(56,80),'R30':(61,80),'C21':(49,88),'J9':(59,94),'C12':(65,33),'R24':(70,36),'C13':(70,40),'R25':(70,43),'C24':(79,59)},
        'hf': {'C11':(88,24),'C21':(40,35),'D1':(104,66),'C7':(36,31),'C10':(73,15)},
        'vhf': {'C3':(7,33),'C4':(7,38),'R3':(53,42),'C8':(53,46),'R4':(20,50),'C1':(33,58)},
    }
    positions['uhf']=positions['vhf']
    for board in result:
        for part in board.parts:
            if part['ref'] in positions.get(board.name,{}): part['x'],part['y']=positions[board.name][part['ref']]
            if board.name=='control' and part['ref']=='J4': part['rotation']=270
    return result

def write():
    data=[dict(name=b.name,width_mm=b.width,height_mm=b.height,layers=b.layers,parts=b.parts,filters=b.filters,notes=b.notes) for b in boards()]
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'design.json').write_text(json.dumps(data,indent=2)+'\n')
    with (OUT/'bom.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=['board','ref','value','mpn','footprint','source','status'])
        writer.writeheader()
        for b in data:
            for p in b['parts']:
                if p['footprint']: writer.writerow({**{k:p[k] for k in ['ref','value','mpn','footprint','source']},'board':b['name'],'status':'prototype; procurement and independent review pending'})
    print({b['name']:len([p for p in b['parts'] if p['footprint']]) for b in data})

if __name__=='__main__': write()
