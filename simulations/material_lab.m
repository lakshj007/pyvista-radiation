% SPDX-License-Identifier: MIT
% Independently authored larger material lab. Parameters come from the archived JSON.
pkg load csxcad;
pkg load openems;
recipe = jsondecode(fileread(getenv('MATERIAL_LAB_CONFIG')));
kind = getenv('MATERIAL_LAB_CASE');
step = str2double(getenv('MATERIAL_LAB_STEP_MM'));
out = getenv('MATERIAL_LAB_OUTPUT');
if ~isfinite(step) || step <= 0 || exist(out, 'dir'), error('Invalid or existing output'); end
mkdir(out);
cases = recipe.cases;
if ~iscell(cases), cases = num2cell(cases); end
material = [];
for k=1:numel(cases)
    if strcmp(cases{k}.key, kind), material = cases{k}; end
end
if isempty(material), error('Unknown material case'); end

f0 = recipe.frequency_hz;
FDTD = InitFDTD('NrTS', recipe.max_timesteps, 'EndCriteria', recipe.end_criterion);
FDTD = SetGaussExcite(FDTD, f0, recipe.pulse_corner_hz);
FDTD = SetBoundaryCond(FDTD, {'PML_8','PML_8','PML_8','PML_8','PML_8','PML_8'});
CSX = InitCSX();
domain = 1000 * recipe.domain_bounds_m;
mesh.x = domain(1):step:domain(2);
mesh.y = domain(3):step:domain(4);
mesh.z = domain(5):step:domain(6);
if step < recipe.step_mm
    % Refine between exact geometry anchors; overlaying two uniform grids
    % would introduce accidental 1-2 mm sliver cells and tiny timesteps.
    mesh.x = []; mesh.y = []; mesh.z = [];
end
mesh.x = SmoothMeshLines(unique([mesh.x domain(1) domain(2) -610 -600 -590 -300 0 20 60 100 120 650]), step, 1.5);
mesh.y = SmoothMeshLines(unique([mesh.y domain(3) domain(4) -500 -10 0 10 500 550]), step, 1.5);
mesh.z = SmoothMeshLines(unique([mesh.z domain(5) domain(6) -300 -60 -10 0 10 60 300]), step, 1.5);
CSX = DefineRectGrid(CSX, 1e-3, mesh);
CSX = AddMetal(CSX, 'dipole');
CSX = AddBox(CSX, 'dipole', 10, [-610 -10 -60], [-590 10 -10]);
CSX = AddBox(CSX, 'dipole', 10, [-610 -10 10], [-590 10 60]);
[CSX port] = AddLumpedPort(CSX, 20, 1, 50, [-600 0 -10], [-600 0 10], [0 0 1], true);

if ~strcmp(material.model, 'air')
    b = 1000 * material.bounds_m;
    if strcmp(material.model, 'pec')
        CSX = AddMetal(CSX, 'sample');
    elseif strcmp(material.model, 'sheet')
        CSX = AddConductingSheet(CSX, 'sample', material.conductivity_s_per_m, material.thickness_m);
    else
        CSX = AddMaterial(CSX, 'sample');
        CSX = SetMaterialProperty(CSX, 'sample', 'Epsilon', material.relative_permittivity, ...
                                  'Kappa', material.conductivity_s_per_m);
    end
    if strcmp(material.model, 'layered')
        for k=1:rows(material.layers_m)
            CSX = AddBox(CSX, 'sample', 1, ...
                [1000*material.layers_m(k,1) b(3) b(5)], ...
                [1000*material.layers_m(k,2) b(4) b(6)]);
        end
    else
        CSX = AddBox(CSX, 'sample', 1, [b(1) b(3) b(5)], [b(2) b(4) b(6)]);
    end
end
CSX = AddDump(CSX, 'electric', 'DumpType', 10, 'FileType', 1, 'DumpMode', 1, 'Frequency', f0);
r = 1000 * recipe.recording_bounds_m;
CSX = AddBox(CSX, 'electric', 0, [r(1) r(3) r(5)], [r(2) r(4) r(6)]);
WriteOpenEMS([out '/geometry.xml'], FDTD, CSX);
RunOpenEMS(out, 'geometry.xml', '--numThreads=4');
port = calcPort(port, out, f0);
dlmwrite([out '/port.csv'], [f0 real(port.uf.inc) imag(port.uf.inc) ...
    real(port.uf.ref) imag(port.uf.ref) port.P_inc port.P_ref], ',');
fprintf('THROUGH_WALL_FINISHED %s %.6g\n', kind, step);
