"""Small SVG principal-plane plots for the browser comparison."""

import numpy as np

from .numerics import principal_cut


def cut_chart(data, indices, plane, normalization, floor_db):
    """Accessible SVG using the same saved fields and references as the mesh."""
    width, height = 600, 220
    left, right, top, bottom = 45, 585, 20, 185

    def x(t):
        return left + (t + 180) / 360 * (right - left)

    def y(db):
        return bottom - (db - floor_db) / (-floor_db) * (bottom - top)

    items = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{plane} plane radiation cuts">',
        '<rect width="600" height="220" fill="white"/>',
    ]
    for angle in (-180, -90, 0, 90, 180):
        items.append(f'<path d="M{x(angle)},{top} V{bottom}" stroke="#e1e6ea"/>')
        items.append(f'<text x="{x(angle)}" y="205" text-anchor="middle">{angle}°</text>')
    for db in np.linspace(floor_db, 0, int(abs(floor_db) / 10) + 1):
        items.append(f'<path d="M{left},{y(db)} H{right}" stroke="#e1e6ea"/>')
        items.append(f'<text x="38" y="{y(db) + 4}" text-anchor="end">{db:g}</text>')
    for index, color in zip(indices, ("#1574b8", "#cb5b32")):
        angles, db = principal_cut(data, index, plane, normalization, floor_db)
        path = " ".join(
            f"{'M' if i == 0 else 'L'}{x(t):.2f},{y(v):.2f}"
            for i, (t, v) in enumerate(zip(angles, db))
        )
        items.append(f'<path d="{path}" stroke="{color}" stroke-width="2.5" fill="none"/>')
    items.append("</svg>")
    return "".join(items)


def summary(data, indices):
    """Magnitude-only backward/peak values, independent of selected display floor."""
    rows = []
    for index in indices:
        a = data.field_magnitude[index]
        peak = a.max()
        backward = a[-1].mean()
        db = 20 * np.log10(backward / peak) if peak and backward else -np.inf
        rows.append(f"{data.frequency_hz[index] / 1e9:g} GHz: {db:.1f} dB backward / peak")
    return " · ".join(rows)


def metrics_table(data, indices):
    """Frequency, interpolated half-power widths and axial backward level."""
    from .metrics import beamwidth

    rows = [
        "<table><caption>Pattern measurements · interpolated from the saved angular grid</caption><thead><tr><th>Frequency</th><th>xz width</th><th>yz width</th><th>Back / peak</th></tr></thead><tbody>"
    ]
    for index in indices:
        widths = [beamwidth(data, index, p) for p in ("xz", "yz")]
        labels = [f"{w['width_deg']:.1f}°" if w else "Unbounded" for w in widths]
        a = data.field_magnitude[index]
        peak = a.max()
        back = a[-1].mean()
        value = (
            f"{20 * np.log10(back / peak):.1f} dB"
            if peak and back
            else "Undefined"
            if not peak
            else "−∞ dB"
        )
        rows.append(
            f"<tr><td>{data.frequency_hz[index] / 1e9:g} GHz</td><td>{labels[0]}</td><td>{labels[1]}</td><td>{value}</td></tr>"
        )
    return "".join(rows) + "</tbody></table>"
