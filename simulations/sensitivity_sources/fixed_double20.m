% Controlled sensitivity variant fixed_double20; modified 2026-10-24. GPL-3.0-or-later.
% SPDX-License-Identifier: GPL-3.0-or-later
% Adapted 2026-10-22: headless full-sphere, three frequencies, raw reference cuts.
%% Simple Patch Antenna Tutorial
%% -----------------------------
%% This tutorial simulates a microstrip patch antenna on a low-loss dielectric
%% substrate, covering the full workflow from geometry setup to S-parameter
%% extraction and far-field pattern analysis. It introduces the key openEMS
%% building blocks — CSXCAD geometry, lumped port excitation, automatic meshing,
%% and the near-field-to-far-field transformation — in a single self-contained
%% example.
%
% Tested with
%  - Octave 11.3
%  - openEMS v0.37
%
% (C) 2010-2026 Thorsten Liebig <thorsten.liebig@gmx.de>

pkg load csxcad;
pkg load openems;

%% Setup the Simulation
%% --------------------
%% Define the physical dimensions and material properties of the patch,
%% substrate, and ground plane. The patch ``width`` controls the resonant
%% frequency — a narrower patch resonates higher — while the substrate
%% permittivity ``epsR`` and thickness together set the effective wavelength
%% inside the dielectric. The ``SimBox`` must be large enough that the
%% absorbing boundaries sit well away from the antenna near-field region.
physical_constants;
unit = 1e-3; % all length in mm

% patch width in x-direction
patch.width  = 32; % resonant length
% patch length in y-direction
patch.length = 40;

%substrate setup
substrate.epsR   = 3.38;
substrate.kappa  = 1e-3 * 2*pi*2.45e9 * EPS0*substrate.epsR;
substrate.width  = 60;
substrate.length = 60;
substrate.thickness = 1.524;
substrate.cells = 4;

%setup feeding
feed.pos = -6; %feeding position in x-direction
feed.R = 50;     %feed resistance

% size of the simulation box
SimBox = [200 200 150]*1;

%% Setup FDTD Parameter & Excitation Function
%% ------------------------------------------
%% Configure the broadband Gaussian pulse and the first-order Mur absorbing
%% boundary conditions. The centre frequency ``f0`` and 20 dB bandwidth ``fc``
%% should bracket the expected patch resonance so that the full S-parameter
%% response is captured in a single simulation run. Mur boundaries are chosen
%% here because the antenna sits well inside the box; switch to PML if you
%% need stronger absorption for a more compact simulation domain.
f0 = 2e9; % center frequency
fc = 1e9; % 20 dB corner frequency
FDTD = InitFDTD( 'NrTs', 60000, 'EndCriteria', 1e-30 );
FDTD = SetGaussExcite( FDTD, f0, fc );
BC = {'MUR' 'MUR' 'MUR' 'MUR' 'MUR' 'MUR'}; % boundary conditions
FDTD = SetBoundaryCond( FDTD, BC );

%% Setup CSXCAD Geometry & Mesh
%% ----------------------------
%% Build the complete antenna structure — patch metal, dielectric substrate,
%% ground plane, lumped feed port, and the NF2FF integration surface — inside
%% a single CSXCAD container. The mesh is generated with ``DetectEdges`` and
%% ``SmoothMesh``: patch edges are resolved at lambda/50 to capture the patch
%% current distribution accurately, while the surrounding free-space region
%% uses the coarser lambda/20 spacing to keep the total cell count manageable.
CSX = InitCSX();

%initialize the mesh with the "air-box" dimensions
mesh.x = [-SimBox(1)/2 SimBox(1)/2];
mesh.y = [-SimBox(2)/2 SimBox(2)/2];
mesh.z = [-SimBox(3)/3 SimBox(3)*2/3];

% Create Patch
CSX = AddMetal( CSX, 'patch' ); % create a perfect electric conductor (PEC)
start = [-patch.width/2 -patch.length/2 substrate.thickness];
stop  = [ patch.width/2  patch.length/2 substrate.thickness];
CSX = AddBox(CSX,'patch',10,start,stop); % add a box-primitive to the metal property 'patch'

% Create Substrate
CSX = AddMaterial( CSX, 'substrate' );
CSX = SetMaterialProperty( CSX, 'substrate', 'Epsilon', substrate.epsR, 'Kappa', substrate.kappa );
start = [-substrate.width/2 -substrate.length/2 0];
stop  = [ substrate.width/2  substrate.length/2 substrate.thickness];
CSX = AddBox( CSX, 'substrate', 0, start, stop );

% add extra cells to discretize the substrate thickness
mesh.z = [linspace(0,substrate.thickness,substrate.cells+1) mesh.z];

% Create Ground same size as substrate
CSX = AddMetal( CSX, 'gnd' ); % create a perfect electric conductor (PEC)
start(3)=0;
stop(3) =0;
CSX = AddBox(CSX,'gnd',10,start,stop);

% Apply the Excitation & Resist as a Current Source
start = [feed.pos 0 0];
stop  = [feed.pos 0 substrate.thickness];
[CSX port] = AddLumpedPort(CSX, 5 ,1 ,feed.R, start, stop, [0 0 2], true);

% Finalize the Mesh
% detect all edges except of the patch
mesh = DetectEdges(CSX, mesh,'ExcludeProperty','patch');
% detect and set a special 2D metal edge mesh for the patch
mesh = DetectEdges(CSX, mesh,'SetProperty','patch','2D_Metal_Edge_Res', c0/(f0+fc)/unit/50.0);
% generate a smooth mesh with max. cell size: lambda_min / 20
mesh = SmoothMesh(mesh, c0/(f0+fc)/unit/20);
CSX = DefineRectGrid(CSX, unit, mesh);

% add a nf2ff calc box; size is 3 cells away from MUR boundary condition
start = [mesh.x(4)     mesh.y(4)     mesh.z(4)];
stop  = [mesh.x(end-3) mesh.y(end-3) mesh.z(end-3)];
[CSX nf2ff] = CreateNF2FFBox(CSX, 'nf2ff', start, stop);

%% Prepare and Run Simulation
%% --------------------------
%% Write the geometry and solver settings to an XML file, optionally preview
%% the structure in AppCSXCAD, then launch the openEMS solver. Inspecting the
%% geometry plot before running is strongly recommended: it lets you verify
%% patch, substrate, and port placement immediately, without waiting for the
%% solver to finish.

Sim_Path = '/work/simulations/work/sensitivity/fixed_double20';
WriteOpenEMS([Sim_Path '/geometry.xml'], FDTD, CSX);
RunOpenEMS(Sim_Path, 'geometry.xml', '--numThreads=4');

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
