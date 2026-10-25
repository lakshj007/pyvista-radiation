"""Reproducible solver sensitivity experiment, run inside the solver container.

Uses the attributed GPL tutorial recipe in generate_patch.m. Generated Octave
sources retain its notices and stay under simulations/work/sensitivity/.
"""
from pathlib import Path
import json
import subprocess
import hashlib
import sys
import re

import h5py
import numpy as np

ROOT = Path('/work')
OUT = ROOT/'data/sensitivity'
OUT.mkdir(exist_ok=True)
recipe = (ROOT/'simulations/generate_patch.m').read_text()
prefix = recipe[:recipe.index('Sim_Path =')].replace("'NrTs', 30000", "'NrTs', 90000")
cases = [
    dict(name='mur20', cells=20, substrate=4, boundary='MUR', amplitude=1, box=1),
    dict(name='mur25', cells=25, substrate=6, boundary='MUR', amplitude=1, box=1),
    dict(name='mur30', cells=30, substrate=8, boundary='MUR', amplitude=1, box=1),
    dict(name='pml20', cells=20, substrate=4, boundary='PML_8', amplitude=1, box=1),
    dict(name='large20', cells=20, substrate=4, boundary='MUR', amplitude=1, box=1.5),
    dict(name='double20', cells=20, substrate=4, boundary='MUR', amplitude=2, box=1),
    dict(name='fixed20', cells=20, substrate=4, boundary='MUR', amplitude=1, box=1, fixed_steps=60000),
    dict(name='fixed_double20', cells=20, substrate=4, boundary='MUR', amplitude=2, box=1, fixed_steps=60000),
]
for case in cases:
    name = case['name']
    log_path = OUT/f'{name}.log'
    prior_log = log_path.read_text() if log_path.exists() else ''
    finished = (f"Time for {case['fixed_steps']} iterations" in prior_log
                if case.get('fixed_steps') else 'Warning: Max.' not in prior_log)
    if (OUT/f'{name}.npz').exists() and (OUT/f'{name}.npz').stat().st_mtime >= log_path.stat().st_mtime and finished and re.search(r'Time for \d+ iterations',prior_log) and '--force' not in sys.argv:
        print('Reusing completed', name, flush=True)
        continue
    work = ROOT/'simulations/work/sensitivity'/name
    work.mkdir(parents=True,exist_ok=True)
    source = (f'% Controlled sensitivity variant {name}; modified 2026-10-24. GPL-3.0-or-later.\n' + prefix).replace('substrate.cells = 4;', f"substrate.cells = {case['substrate']};")
    source = source.replace('SimBox = [200 200 150];', f"SimBox = [200 200 150]*{case['box']};")
    source = source.replace('/unit/50', f"/unit/{2.5*case['cells']}").replace('/unit/20', f"/unit/{case['cells']}")
    source = source.replace("'MUR'", f"'{case['boundary']}'")
    source = source.replace('[0 0 1], true)', f"[0 0 {case['amplitude']}], true)")
    if case['boundary']=='PML_8':
        source=source.replace('mesh.x(4)', 'mesh.x(10)').replace('mesh.y(4)', 'mesh.y(10)').replace('mesh.z(4)', 'mesh.z(10)').replace('end-3','end-9')
    source+=f"\nSim_Path = '{work}';\nWriteOpenEMS([Sim_Path '/geometry.xml'], FDTD, CSX);\nRunOpenEMS(Sim_Path, 'geometry.xml', '--numThreads=4');\n"
    if case.get('fixed_steps'):
        source=source.replace("'NrTs', 90000", "'NrTs', 60000, 'EndCriteria', 1e-30")
    source+='''
freq = [2.2e9 2.4e9 2.6e9];
result = CalcNF2FF(nf2ff, Sim_Path, freq, (-180:2:180)*pi/180, [0 90]*pi/180, ...
    'Center', [0 0 1e-3], 'Radius', 1, 'Outfile', 'cuts.h5', 'Mode', 1);
port = calcPort(port, Sim_Path, freq);
et = load([Sim_Path '/et']);
excitation = DFT_time2freq(et(:,1), et(:,2), freq);
s11 = port.uf.ref ./ port.uf.inc;
pin = port.P_inc;
pacc = port.P_acc;
dlmwrite([Sim_Path '/port.csv'], [freq(:),real(s11(:)),imag(s11(:)),pin(:),pacc(:),real(excitation(:)),imag(excitation(:))], ',');
'''
    script = work/'run.m'
    script.write_text(source)
    log = OUT/f'{name}.log'
    print('Running',name,flush=True)
    with log.open('w') as stream:
        subprocess.run(['octave','--no-gui','--quiet',str(script)],stdout=stream,stderr=subprocess.STDOUT,check=True)
    h5 = work/'cuts.h5'
    arrays={}
    with h5py.File(h5) as f:
        arrays['theta_rad']=f['Mesh/theta'][:]
        for component in ('E_theta','E_phi'):
            arrays[component.lower()]=np.array([(f[f'nf2ff/{component}/FD/f{i}_real'][:]+1j*f[f'nf2ff/{component}/FD/f{i}_imag'][:]).T for i in range(3)])
        arrays['prad_raw']=f['nf2ff'].attrs['Prad']
        arrays['dmax_planes']=f['nf2ff'].attrs['Dmax']
    arrays['port']=np.loadtxt(work/'port.csv',delimiter=',')
    temporary=OUT/f'{name}.npz.tmp'
    with temporary.open('wb') as stream:
        np.savez_compressed(stream,**arrays)
    temporary.replace(OUT/f'{name}.npz')
    (OUT/f'{name}.xml').write_bytes((work/'geometry.xml').read_bytes())
    sources=ROOT/'simulations/sensitivity_sources'
    sources.mkdir(exist_ok=True)
    (sources/f'{name}.m').write_text(source)
manifest=dict(cases=cases,solver_version=subprocess.check_output(['dpkg-query','-W','-f=${Version}','openems'],text=True),
    date='2026-10-24',runner_snapshot_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    case_source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'simulations/sensitivity_sources').glob('*.m')},recipe_sha256=hashlib.sha256(recipe.encode()).hexdigest(),
    angles='signed theta -180:2:180 deg, phi 0 and 90 deg',
    notes='Controlled sensitivity checks, not a measurement validation or proof of asymptotic convergence.')
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
