% SPDX-License-Identifier: MIT
% Independent small full-wave wall experiment. No propagation-map approximation.
pkg load csxcad;
pkg load openems;

kind = getenv('WALL_CASE');
step = str2double(getenv('WALL_GRID_MM'));
out = getenv('WALL_OUTPUT');
if ~any(strcmp(kind, {'air', 'dielectric', 'metal'})) || ~isfinite(step) || step <= 0
    error('Set WALL_CASE, WALL_GRID_MM and WALL_OUTPUT using run_through_wall.py');
end
if exist(out, 'dir'), error('Output directory already exists: %s', out); end
mkdir(out);

f0 = 2.4e9;
FDTD = InitFDTD('NrTS', 12000, 'EndCriteria', 1e-6);
FDTD = SetGaussExcite(FDTD, f0, 0.4e9);
FDTD = SetBoundaryCond(FDTD, {'PML_8','PML_8','PML_8','PML_8','PML_8','PML_8'});
CSX = InitCSX();
mesh.x = -400:step:400;
mesh.y = -300:step:300;
mesh.z = -200:step:200;
mesh.x = unique([mesh.x -225 -220 -215 0 80]);
mesh.y = unique([mesh.y -200 -5 0 5 200]);
mesh.z = unique([mesh.z -120 -25 -5 0 5 25 120]);
mesh.x = SmoothMeshLines(mesh.x, step, 1.5);
mesh.y = SmoothMeshLines(mesh.y, step, 1.5);
mesh.z = SmoothMeshLines(mesh.z, step, 1.5);
CSX = DefineRectGrid(CSX, 1e-3, mesh);

% A small fat PEC dipole: 50 mm total height, 10 mm square arms, 10 mm
% resistively fed gap. The 50-ohm port absorbs residual source-region fields.
% This is an explicit numerical antenna, not a calibrated commercial radio.
CSX = AddMetal(CSX, 'dipole');
CSX = AddBox(CSX, 'dipole', 10, [-225 -5 -25], [-215 5 -5]);
CSX = AddBox(CSX, 'dipole', 10, [-225 -5 5], [-215 5 25]);
[CSX port] = AddLumpedPort(CSX, 20, 1, 50, [-220 0 -5], [-220 0 5], [0 0 1], true);

wall_start = [0 -200 -120];
wall_stop = [80 200 120];
if strcmp(kind, 'dielectric')
    CSX = AddMaterial(CSX, 'wall');
    % Illustrative constant material; no claim that it represents measured concrete.
    CSX = SetMaterialProperty(CSX, 'wall', 'Epsilon', 4, 'Kappa', 0.03);
    CSX = AddBox(CSX, 'wall', 1, wall_start, wall_stop);
elseif strcmp(kind, 'metal')
    CSX = AddMetal(CSX, 'wall');
    CSX = AddBox(CSX, 'wall', 1, wall_start, wall_stop);
end

% Record a horizontal complex E-field slice through the 3D simulation. PML
% layers are outside this recording region. Node interpolation keeps Ez
% tangential to the wall interfaces; normal Ex at the interface is less exact.
CSX = AddDump(CSX, 'electric', 'DumpType', 10, 'FileType', 1, ...
              'DumpMode', 1, 'Frequency', f0);
CSX = AddBox(CSX, 'electric', 0, [-340 -240 0], [340 240 0]);
WriteOpenEMS([out '/geometry.xml'], FDTD, CSX);
RunOpenEMS(out, 'geometry.xml', '--numThreads=4');
port = calcPort(port, out, f0);
dlmwrite([out '/port.csv'], [f0, real(port.uf.inc), imag(port.uf.inc), ...
    real(port.uf.ref), imag(port.uf.ref), port.P_inc, port.P_ref], ',');
fprintf('THROUGH_WALL_FINISHED %s %.6g\n', kind, step);
