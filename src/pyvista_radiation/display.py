"""Compatibility helpers for the initial preview."""

from .mesh import radiation_mesh
from .numerics import amplitude_db, frequency_index, reference_amplitude


def normalized_field(data, frequency_index_):
    index = frequency_index(data, frequency_index_)
    return data.field_magnitude[index] / reference_amplitude(data, index)


def field_db(data, frequency_index_, floor_db=-40):
    index = frequency_index(data, frequency_index_)
    return amplitude_db(data.field_magnitude[index], reference_amplitude(data, index), floor_db)


def preview_mesh(data, frequency_index):
    return radiation_mesh(data, frequency_index)
