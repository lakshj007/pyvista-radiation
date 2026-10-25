"""Convert this example's legacy NF2FF files; h5py is a generation-only dependency."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from pyvista_radiation import RadiationData, save
from pyvista_radiation.model import CONVENTION

root = Path(__file__).resolve().parents[1]
raw = root / 'data/raw'
fields = [[], []]
waveform = np.loadtxt(raw/'excitation.csv')
frequencies = np.array([2.2e9,2.4e9,2.6e9])
dt = waveform[1,0]-waveform[0,0]
spectrum = 2*dt*(np.exp(-2j*np.pi*frequencies[:,None]*waveform[:,0]) @ waveform[:,1])
if np.any(abs(spectrum)<1e-20):
    raise ValueError('Excitation spectrum is too small for calibration')
power, directivity = [], []
for i in range(1, 4):
    with h5py.File(raw / f'patch_{i}.h5') as f:
        np.testing.assert_allclose(f['nf2ff'].attrs['Frequency'], [2.2e9,2.4e9,2.6e9][i-1], rtol=1e-7)
        np.testing.assert_allclose(f['Mesh/r'][:], 1.0)
        theta = np.deg2rad(np.arange(0,181,5,dtype=float))
        phi = np.deg2rad(np.arange(0,360,5,dtype=float))
        np.testing.assert_allclose(f['Mesh/theta'][:].ravel(), theta, atol=2e-7)
        np.testing.assert_allclose(f['Mesh/phi'][:].ravel(), phi, atol=3e-7)
        for out, name in zip(fields, ['E_theta', 'E_phi']):
            grp = f[f'nf2ff/{name}/FD']
            out.append((grp['f0_real'][:] + 1j*grp['f0_imag'][:]).T/spectrum[i-1])
        power.append(float(np.asarray(f['nf2ff'].attrs['Prad']).item())/abs(spectrum[i-1])**2)
        directivity.append(float(np.asarray(f['nf2ff'].attrs['Dmax']).item()))
version = subprocess.check_output(['dpkg-query', '-W', '-f=${Version}', 'openems'], text=True)
metadata = dict(schema_version=1, angle_convention=CONVENTION, angle_unit='rad',
    frequency_unit='Hz', field_unit='V/m', array_order=['frequency','theta','phi'],
    reference_radius_m=1.0, normalization='none',
    provenance=dict(kind='simulation', source='openEMS Simple Patch Antenna tutorial',
        generator='simulations/generate_patch.m + simulations/export_npz.py',
        solver_version=version, upstream_commit='53a426429809ade506828c0aadb550589a115ee5',
        generation_date='2026-10-22',
        angular_coordinates='Exact requested grid; raw HDF5 axes are float32 rounded copies',
        amplitude_reference='Steady response to the tutorial source with unit-amplitude temporal envelope; not incident-power normalized',
        calibration=dict(date='2026-10-24', algorithm='E_raw / S(f); Prad_raw / abs(S(f))**2',
                         source='data/raw/excitation.csv',
                         spectrum_seconds_real=spectrum.real.tolist(),
                         spectrum_seconds_imag=spectrum.imag.tolist(),
                         dft='S(f) = 2*dt*sum(et(t)*exp(-2*pi*i*f*t)); matches openEMS pulse DFT convention'),
        end_criterion=1e-5,
        generator_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                          [root/'simulations/generate_patch.m', Path(__file__)]}, license='CC0-1.0 (numerical outputs)',
        source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(raw.glob('*'))},
        antenna=dict(patch_mm=[32,40], substrate_mm=[60,60,1.524], eps_r=3.38,
                     loss_tangent_reference=0.001, loss_reference_hz=2.45e9,
                     feed_x_mm=-6, feed_resistance_ohm=50, phase_center_m=[0,0,0.001],
                     box_mm=[200,200,150], boundaries='MUR', max_timesteps=30000)))
data = RadiationData(np.array([2.2e9,2.4e9,2.6e9]), theta, phi,
                     np.array(fields[0]), np.array(fields[1]), metadata,
                     np.array(power), np.array(directivity))
save(root/'data/patch_reference.npz', data)
(root/'data/patch_reference.json').write_text(json.dumps(metadata, indent=2)+'\n')
print(data.field_magnitude.shape, 'Dmax:', directivity, 'Prad:', power)
cut_fields = []
for i in range(1,4):
    with h5py.File(raw/f'cuts_{i}.h5') as f:
        components = []
        for name in ['E_theta','E_phi']:
            g = f[f'nf2ff/{name}/FD']
            components.append((g['f0_real'][:] + 1j*g['f0_imag'][:]).T)
        cut_fields.append(np.hypot(np.abs(components[0]),np.abs(components[1])))
        cut_theta = f['Mesh/theta'][:].ravel()
np.savez_compressed(root/'data/reference_cuts.npz', theta_rad=cut_theta,
                    field_magnitude=np.array(cut_fields)/abs(spectrum[:,None,None]), frequency_hz=data.frequency_hz)
