# Draft: example proposal for PyVista maintainers

This proposal is prepared for review. It has not been submitted upstream.

**Suggested title:** Example proposal: visualize recorded openEMS pulses through two floors

I would like to contribute a focused example showing how PyVista can visualize saved electromagnetic simulation results from openEMS. Would this fit the example gallery, or would an external-example listing be more appropriate initially?

The example loads an ordinary VTK `MultiBlock`, clips volume cells to show a house cutaway, slices the walls for an architectural section, and updates a shared `StructuredGrid` scalar array with a recorded-time slider. It runs with PyVista and NumPy, without an openEMS installation, trame server or import of the separate radiation extension. The Python time slider requires a live session; the documentation builds a static snapshot.

The example and assets are available here:

- [Standalone script and instructions](https://github.com/lakshj007/pyvista-radiation/tree/feat/radiation-comparison-validation/examples/house_showcase)
- [Rendered preview](https://github.com/lakshj007/pyvista-radiation/blob/feat/radiation-comparison-validation/preview/house_showcase.png)
- [Complete offline example bundle](https://github.com/lakshj007/pyvista-radiation/blob/feat/radiation-comparison-validation/preview/house_showcase.zip)

The native dataset is approximately 1.5 MB. It retains all 143 original time samples from one vertical Ey recording, with every second spatial point selected for a 100 mm display grid. Selected float32 fields and timestamps are unchanged. The original building boxes and marker coordinates are supplied separately; cutaways change only the picture. Native field data and a manifest retain source provenance and file hashes. Example code is MIT and generated numerical data are CC0-1.0.

The physical model is a compact 4 × 3 m two-level structure at 500 MHz, with assumed homogeneous partitions and wood-class slabs. It is an illustrative solver dataset without house-specific mesh convergence or measurement validation. It does not provide full-volume fields, received dBm or a calibrated house/Wi-Fi coverage prediction.

The script is formatted as a Sphinx-Gallery example and is exercised by our documentation build. The standalone folder also renders in a fresh environment outside the checkout with only PyVista and NumPy installed. Tests verify the selected samples and original timestamps, dataset hashes, geometry/marker coordinates and in-place frame changes with camera/actor retention.

If a gallery contribution is a good fit, I can adapt the asset layout to `pyvista/data` and the standard dataset download wrapper, following your preferred category and review process. This proposal is limited to a visualization example and dataset; it introduces no RF solver dependency or new propagation algorithm into PyVista.
