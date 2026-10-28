"""Optional synthetic terrain/city propagation example, separate from the core extension."""

from pyvista_radiation.webapp import serve

if __name__ == "__main__":
    serve(coverage=True)
