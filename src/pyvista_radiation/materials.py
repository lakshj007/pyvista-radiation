"""Reproducible material comparison recipe, not a catalog of measured products."""

ITU_SOURCE = "https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.2040-4-202509-I%21%21PDF-E.pdf"


def material_lab_config():
    """A larger 1 GHz slab experiment using P.2040-4 Table 3 material examples.

    Constant epsilon and conductivity are evaluated at the recording frequency;
    this does not implement broadband material dispersion. The thin resistive
    sheet is a stated synthetic example of openEMS AddConductingSheet.
    """
    bounds = [0, 0.12, -0.5, 0.5, -0.3, 0.3]

    def bulk(key, label, epsilon, sigma, exponent):
        return dict(key=key, label=label, model="bulk", bounds_m=bounds.copy(),
                    relative_permittivity=epsilon, conductivity_s_per_m=sigma,
                    conductivity_frequency_exponent=exponent,
                    source="ITU-R P.2040-4 (2025), Table 3, evaluated at 1 GHz",
                    description="120 mm equal-thickness reference slab; material-class example, not a measured product")

    cases = [dict(key="air", label="Air baseline", model="air", description="No slab"),
             bulk("wood", "Wood", 1.99, 0.0047, 1.0718),
             bulk("glass", "Glass", 6.31, 0.0036, 1.3394),
             bulk("brick", "Brick", 3.91, 0.0238, 0.16),
             bulk("concrete", "Concrete", 5.24, 0.0462, 0.7822)]
    cases += [dict(key="layered_glass", label="Glass / air / glass", model="layered",
                   bounds_m=bounds.copy(), relative_permittivity=6.31,
                   conductivity_s_per_m=0.0036,
                   layers_m=[[0, 0.02], [0.10, 0.12]],
                   source="Glass coefficients: ITU-R P.2040-4 Table 3; stack geometry is illustrative",
                   description="Two 20 mm glass panes with an 80 mm air gap; not the same glass volume as the solid slab"),
              dict(key="sheet", label="Resistive conducting sheet", model="sheet",
                   bounds_m=[0.06, 0.06, -0.5, 0.5, -0.3, 0.3],
                   conductivity_s_per_m=10000, thickness_m=0.0001,
                   sheet_resistance_ohm_per_square=1,
                   source="Synthetic thin-sheet parameters using openEMS AddConductingSheet",
                   description="Zero-thickness simulation surface representing a 100 micrometre resistive film; not a 120 mm slab"),
              dict(key="metal", label="Perfect metal (PEC)", model="pec",
                   bounds_m=bounds.copy(), source="openEMS AddMetal",
                   description="Ideal opaque conductor, not finite-conductivity steel or copper")]
    return dict(
        title="Material wave lab", frequency_hz=1e9, pulse_corner_hz=0.15e9,
        domain_bounds_m=[-1.2, 1.2, -0.8, 0.8, -0.5, 0.5],
        wall_bounds_m=bounds, recording_bounds_m=[-1.05, 1.05, -0.65, 0.65, 0, 0],
        source_xyz_m=[-0.6, 0, 0], source_length_m=0.12,
        receiver_xyz_m=[[-0.3, 0, 0], [0.65, 0, 0], [0.65, 0.55, 0]],
        receiver_names=["Before slab", "Behind slab", "Beside slab edge"],
        step_mm=10, end_criterion=1e-6, max_timesteps=20000,
        cases=cases, material_reference=ITU_SOURCE,
    )
