"""Circuit calculations and ngspice AC tests. Models are not physical RF measurements."""
from pathlib import Path
import json
import math
import os
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from design import OUT, boards

SPICE=Path(os.environ.get('SKYWAVE_NGSPICE',str(Path.home()/'.local/opt/skywave-spice/root/usr/bin/ngspice')))
SIM=OUT/'simulation'

def network(freq,c_pf,l_nh,qfactor=35):
    omega=2*np.pi*np.asarray(freq)
    matrix=np.broadcast_to(np.eye(2,dtype=complex),omega.shape+(2,2)).copy()
    for i,cap in enumerate(c_pf):
        shunt=np.broadcast_to(np.eye(2,dtype=complex),omega.shape+(2,2)).copy()
        shunt[...,1,0]=1j*omega*cap*1e-12
        matrix=matrix@shunt
        if i<len(l_nh):
            series=np.broadcast_to(np.eye(2,dtype=complex),omega.shape+(2,2)).copy()
            series[...,0,1]=1j*omega*l_nh[i]*1e-9+omega*l_nh[i]*1e-9/qfactor
            matrix=matrix@series
    s21=2/(matrix[...,0,0]+matrix[...,0,1]/50+matrix[...,1,0]*50+matrix[...,1,1])
    return 20*np.log10(np.maximum(abs(s21),1e-15))

def spice_filter(spec):
    name=spec['name']; fmin,fmax=spec['passband_hz']
    lines=[f'SkyWave {name} nominal LPF; ideal LC, 50 ohm terminations',
           'V1 source 0 AC 1','RS source n0 50','RL n3 0 50']
    for i,c in enumerate(spec['c_pf']):
        lines.append(f'C{i+1} n{i} 0 {c}p')
        if i<3:lines.append(f'L{i+1} n{i} n{i+1} {spec["l_nh"][i]}n')
    lines+=['.control','set wr_singlescale','set wr_vecnames',
        f'ac dec 150 {fmin/3} {fmax*4}','let s21_db = db(v(n3)*2)',
        f'wrdata {name}.dat s21_db','quit','.endc','.end']
    (SIM/(name+'.cir')).write_text('\n'.join(lines)+'\n')
    run=subprocess.run([str(SPICE),'-b',name+'.cir'],cwd=SIM,capture_output=True,text=True,timeout=60)
    (SIM/(name+'.log')).write_text(run.stdout+run.stderr)
    if run.returncode:raise RuntimeError('ngspice failed for '+name)
    data=np.loadtxt(SIM/(name+'.dat'),skiprows=1)
    analytical=network(data[:,0],spec['c_pf'],spec['l_nh'],1e15)
    difference=float(np.max(abs(data[:,1]-analytical)))
    assert difference<1e-4,(name,difference)
    return difference

def run():
    SIM.mkdir(parents=True,exist_ok=True)
    result={'model_limits':['LC models omit PCB parasitics and inductor self-resonance.',
        'Q=35 is an analysis assumption, not a guaranteed component specification.',
        'Monte Carlo uses independent uniform +/-5% L/C tolerances.',
        'These tests do not establish emissions compliance, sensitivity or output power.'],
        'ngspice_version':subprocess.check_output([str(SPICE),'--version'],text=True).splitlines()[1],
        'filters':{}}
    fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    rng=np.random.default_rng(20261012)
    for ax,spec in zip(axes.flat,[f for b in boards() for f in b.filters]):
        low,high=spec['passband_hz']
        freq=np.geomspace(low/3,high*4,900)
        response=network(freq,spec['c_pf'],spec['l_nh'])
        worst_loss=[];second=[]
        band_freq=np.linspace(low,high,51)
        for _ in range(300):
            caps=np.array(spec['c_pf'])*rng.uniform(.95,1.05,4)
            inds=np.array(spec['l_nh'])*rng.uniform(.95,1.05,3)
            worst_loss.append(float(-network(band_freq,caps,inds).min()))
            second.append(float(-network([2*low],caps,inds)[0]))
        report=dict(passband_hz=[low,high],nominal_loss_db=float(-network(band_freq,spec['c_pf'],spec['l_nh']).min()),
            monte_carlo_cases=300,worst_loss_db=max(worst_loss),minimum_second_harmonic_attenuation_db=min(second),
            spice_vs_abcd_max_error_db=spice_filter(spec))
        report['q_sensitivity_nominal_loss_db']={str(q):float(-network(band_freq,spec['c_pf'],spec['l_nh'],q).min()) for q in [10,20,35,50]}
        report['engineering_targets_passed']=report['worst_loss_db']<1.5 and report['minimum_second_harmonic_attenuation_db']>20
        result['filters'][spec['name']]=report
        ax.semilogx(freq/1e6,response,color='#087f8c',lw=2)
        ax.axvspan(low/1e6,high/1e6,color='#ecb22e',alpha=.25,label='Banda alvo')
        ax.set(title=spec['name'].upper(),xlabel='MHz',ylabel='S21 (dB)',ylim=(-80,1))
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('SkyWave D1 — simulação dos filtros (não é medição)',fontsize=15)
    fig.savefig(OUT/'plots/filter_response.png',dpi=180)
    fig.savefig(OUT/'plots/filter_response.pdf')
    # Calculate supply corners explicitly from reference and divider tolerances.
    voltage=[.8*ref*(1+402000*top/(100000*bottom)) for ref in [.985,1.015] for top in [.99,1.01] for bottom in [.99,1.01]]
    result['power']=dict(buck_nominal_v=.8*(1+402000/100000),buck_corner_v=[min(voltage),max(voltage)],
        dra_recommended_v=[3.3,4.5],buck_current_limit_design_a=1.0,dra_low_power_max_a=.55,
        main_ldo_dissipation_w_at_400ma=(5-3.3)*.4,
        thermal_validation='not measured; copper area, enclosure and ambient temperature remain open',
        input_5v_worst_case_a=round(.4+.15+.12+4.02*.55/(4.75*.85)+4.02*.06/(4.75*.85),3))
    assert 3.3<min(voltage)<max(voltage)<4.5
    truth=[]
    for pressed in [0,1]:
        for arm in [0,1]:
            for select in range(4):
                enables=[bool(pressed and arm and select==i) for i in range(3)]
                assert sum(enables)<=1
                truth.append(dict(ptt=pressed,tx_arm=arm,select=select,hf=enables[0],vhf=enables[1],uhf=enables[2]))
    result['ptt_truth_table']=truth
    states=[];q1=q2=0
    for _ in range(8):
        q1,q2=1-q2,q1;states.append(q2*2+q1)
    assert states==[1,3,2,0,1,3,2,0]
    result['quadrature']=dict(select_sequence=states,lo_max_hz=4*29.7e6,
        device_fmax_hz_at_3v_85c=150e6,note='Clock jitter and setup/hold margins require physical validation.')
    result['all_engineering_targets_passed']=all(v['engineering_targets_passed'] for v in result['filters'].values())
    (OUT/'reports/simulation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({name:{k:v for k,v in r.items() if k not in ['passband_hz']} for name,r in result['filters'].items()},indent=2))
    if not result['all_engineering_targets_passed']:raise SystemExit('Filter engineering target failed; revise circuit.')

if __name__=='__main__':run()
