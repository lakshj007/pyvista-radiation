Experimental release preparation
================================

The current milestone is a reviewable visualization example. A PyPI release is
not required to run the standalone showcase. The package has not been published,
and these notes do not represent a production-readiness or solver-accuracy claim.

Already in place
----------------

* Native PyVista integration, explicit field units and saved-data contracts.
* Automated tests for imports, numerical operations, archive integrity and views.
* Wheel/source builds and documentation checks.
* A standalone showcase that runs without the extension or solver.
* Source provenance and numerical-data licenses.

Before an experimental PyPI release
-----------------------------------

* Review the supported public API and minimum dependency versions with users.
* Decide which large recordings belong in optional downloads. The core wheel
  currently bundles several experiments; the compact showcase is separate.
* Check installation, native rendering and cleanup on Linux, macOS and Windows.
  A successful local fresh-environment render covers one macOS environment only.
* Add package metadata, a changelog, contributor instructions and a documented
  supported-version policy.
* Configure a separate TestPyPI rehearsal, trusted publishing and release checks
  once a release is explicitly requested. Keep release credentials out of code.
* Describe the first version as experimental visualization tooling and document
  what is measured, assumed, approximated and unvalidated in each dataset.

Upstream review
---------------

The prepared :download:`proposal <upstream-proposal.md>` seeks feedback on the
appropriate example route. The external showcase and independent extension can
be reviewed before committing to a stable public API or publication schedule.
