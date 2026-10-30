% SPDX-License-Identifier: MIT
% Full 3D FDTD with three frequency-domain planes and a recorded vertical pulse.
pkg load csxcad;
pkg load openems;
recipe = jsondecode(fileread(getenv('HOUSE_CONFIG')));
kind = getenv('HOUSE_CASE');
step = str2double(getenv('HOUSE_STEP_MM'));
out = getenv('HOUSE_OUTPUT');
if ~isfinite(step) || step <= 0 || exist(out,'dir'), error('Invalid or existing output'); end
mkdir(out);
cases = recipe.cases;
if ~iscell(cases), cases = num2cell(cases); end
selected = [];
for k=1:numel(cases)
    if strcmp(cases{k}.key,kind), selected = cases{k}; end
end
if isempty(selected), error('Unknown house case'); end
FDTD = InitFDTD('NrTS',recipe.max_timesteps,'EndCriteria',recipe.end_criterion,'OverSampling',2);
FDTD = SetGaussExcite(FDTD,recipe.frequency_hz,recipe.pulse_corner_hz);
FDTD = SetBoundaryCond(FDTD,{'PML_8','PML_8','PML_8','PML_8','PML_8','PML_8'});
CSX = InitCSX();
d = 1000*recipe.domain_bounds_m;
mesh.x = d(1):step:d(2); mesh.y = d(3):step:d(4); mesh.z = d(5):step:d(6);
if step < recipe.grid_step_mm
    mesh.x=[]; mesh.y=[]; mesh.z=[];
end
mesh.x=SmoothMeshLines(unique([mesh.x d(1) d(2) -2300 -2000 -1900 -1125 -1100 -1075 -600 -400 -50 0 50 400 800 1200 1900 2000 2300]),step,1.5);
mesh.y=SmoothMeshLines(unique([mesh.y d(3) d(4) -1800 -1500 -1400 -500 -400 -125 -25 0 25 125 400 500 1400 1500 1800]),step,1.5);
mesh.z=SmoothMeshLines(unique([mesh.z d(5) d(6) -100 0 150 975 1000 1025 1950 2200 2350 3200 4150 4400 4550 4800]),step,1.5);
CSX=DefineRectGrid(CSX,1e-3,mesh);
materials=recipe.materials;
if ~iscell(materials), materials=num2cell(materials); end
for k=1:numel(materials)
    m=materials{k};
    CSX=AddMaterial(CSX,m.key);
    CSX=SetMaterialProperty(CSX,m.key,'Epsilon',m.epsilon,'Kappa',m.conductivity_s_per_m);
end
boxes=selected.boxes;
if ~iscell(boxes), boxes=num2cell(boxes); end
for k=1:numel(boxes)
    b=1000*boxes{k}.bounds_m;
    CSX=AddBox(CSX,boxes{k}.material,1,[b(1) b(3) b(5)],[b(2) b(4) b(6)]);
end
% Horizontal y-directed dipole has broadside radiation in the vertical x-z cut.
CSX=AddMetal(CSX,'dipole');
CSX=AddBox(CSX,'dipole',10,[-1125 -125 975],[-1075 -25 1025]);
CSX=AddBox(CSX,'dipole',10,[-1125 25 975],[-1075 125 1025]);
[CSX port]=AddLumpedPort(CSX,20,1,50,[-1100 -25 1000],[-1100 25 1000],[0 1 0],true);
slices=recipe.slices;
if ~iscell(slices), slices=num2cell(slices); end
for k=1:numel(slices)
    p=slices{k}; b=1000*p.bounds_m;
    CSX=AddDump(CSX,p.key,'DumpType',10,'FileType',1,'DumpMode',1,'Frequency',recipe.frequency_hz);
    CSX=AddBox(CSX,p.key,0,[b(1) b(3) b(5)],[b(2) b(4) b(6)]);
end
% Only a spatially subsampled vertical plane is recorded in time, not the
% whole volume. Original sampled times are retained; no phase reconstruction.
CSX=AddDump(CSX,'pulse','DumpType',0,'FileType',1,'DumpMode',1,...
            'SubSampling','2,1,2','StopTime',recipe.pulse_stop_time_s);
CSX=AddBox(CSX,'pulse',0,[-2300 0 -100],[2300 0 4800]);
WriteOpenEMS([out '/geometry.xml'],FDTD,CSX);
RunOpenEMS(out,'geometry.xml','--numThreads=4');
port=calcPort(port,out,recipe.frequency_hz);
dlmwrite([out '/port.csv'],[recipe.frequency_hz real(port.uf.inc) imag(port.uf.inc) ...
    real(port.uf.ref) imag(port.uf.ref) port.P_inc port.P_ref],',');
fprintf('THROUGH_WALL_FINISHED %s %.6g\n',kind,step);
