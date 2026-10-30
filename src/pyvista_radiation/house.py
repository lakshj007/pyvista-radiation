"""A compact two-level full-wave experiment and explicit building geometry."""


def house_config():
    """Return a small schematic house, not a measured construction model."""
    walls = []

    def box(name, bounds, material="partition", role="wall"):
        return dict(name=name, bounds_m=bounds, material=material, role=role)

    walls += [box("West exterior", [-2, -1.9, -1.5, 1.5, .15, 4.4]),
              box("East exterior", [1.9, 2, -1.5, 1.5, .15, 4.4]),
              box("Back exterior", [-1.9, 1.9, 1.4, 1.5, .15, 4.4], role="back"),
              box("Front west", [-1.9, -.4, -1.5, -1.4, .15, 4.4], role="front"),
              box("Front east", [.4, 1.9, -1.5, -1.4, .15, 4.4], role="front"),
              box("Front door header", [-.4, .4, -1.5, -1.4, 1.95, 4.4], role="front"),
              box("Ground slab", [-2, 2, -1.5, 1.5, 0, .15], "timber", "floor"),
              box("Roof slab", [-2, 2, -1.5, 1.5, 4.4, 4.55], "timber", "roof")]
    for label, low, high, header in (("Downstairs", .15, 2.2, 1.95),
                                     ("Upstairs", 2.35, 4.4, 4.15)):
        walls += [box(label + " partition south", [-.05, .05, -1.4, -.4, low, high]),
                  box(label + " partition north", [-.05, .05, .4, 1.4, low, high]),
                  box(label + " door header", [-.05, .05, -.4, .4, header, high])]
    opening_floor = [box("Middle floor west", [-2, .4, -1.5, 1.5, 2.2, 2.35], "timber", "floor"),
                     box("Middle floor east", [1.2, 2, -1.5, 1.5, 2.2, 2.35], "timber", "floor"),
                     box("Middle floor south", [.4, 1.2, -1.5, -.5, 2.2, 2.35], "timber", "floor"),
                     box("Middle floor north", [.4, 1.2, .5, 1.5, 2.2, 2.35], "timber", "floor")]
    closed_floor = [box("Solid middle floor", [-2, 2, -1.5, 1.5, 2.2, 2.35], "timber", "floor")]
    return dict(
        title="Two-floor wave house", frequency_hz=500e6, pulse_corner_hz=100e6,
        domain_bounds_m=[-2.6, 2.6, -2.1, 2.1, -.45, 5.15],
        footprint_m=[4, 3], height_m=4.55, grid_step_mm=25,
        end_criterion=1e-6, max_timesteps=16000, pulse_stop_time_s=55e-9,
        source_xyz_m=[-1.1, 0, 1], source_length_m=.25, source_axis="y",
        receiver_xyz_m=[[-.6, 0, 1], [-1.1, 0, 3.2], [.8, 0, 3.2]],
        receiver_names=["Downstairs", "Upstairs above transmitter", "Upstairs by opening"],
        stair_opening_bounds_m=[.4, 1.2, -.5, .5, 2.2, 2.35],
        materials=[dict(key="partition", epsilon=2.5, conductivity_s_per_m=.005,
                        description="Assumed homogeneous partition; not measured plasterboard"),
                   dict(key="timber", epsilon=1.99,
                        conductivity_s_per_m=.0047 * .5 ** 1.0718,
                        description="Wood-class example evaluated at 0.5 GHz; isotropic constant snapshot",
                        source="ITU-R P.2040-4 Table 3 wood model")],
        cases=[dict(key="open", label="House · open stairwell", boxes=walls + opening_floor),
               dict(key="closed", label="House · solid middle floor", boxes=walls + closed_floor),
               dict(key="air", label="Air baseline", boxes=[])],
        slices=[dict(key="vertical", label="Vertical cut through stairwell", axes=[0, 2], fixed_axis=1,
                     fixed_m=0, bounds_m=[-2.3, 2.3, 0, 0, -.1, 4.8]),
                dict(key="downstairs", label="Downstairs · z = 1 m", axes=[0, 1], fixed_axis=2,
                     fixed_m=1, bounds_m=[-2.3, 2.3, -1.8, 1.8, 1, 1]),
                dict(key="upstairs", label="Upstairs · z = 3.2 m", axes=[0, 1], fixed_axis=2,
                     fixed_m=3.2, bounds_m=[-2.3, 2.3, -1.8, 1.8, 3.2, 3.2])],
        assumptions="Compact schematic two-level structure; homogeneous isotropic partitions and timber slabs, no glazing, furniture, reinforcement or measured construction. A floor opening represents a stairwell void; no stairs are modeled. 500 MHz, not a Wi-Fi band.",
    )
