"""Compile the script-free Arrival passes RML to the Rive v7 runtime format.

Only the baseline object and property types used by scene.rml are supported.
Type and property keys follow Rive's public runtime schema.
"""

import struct
import xml.etree.ElementTree as XML
from pathlib import Path

COMPONENTS = {
    "Node": 2, "Shape": 3, "Ellipse": 4, "Rectangle": 7,
    "SolidColor": 18, "Fill": 20, "Stroke": 24,
}
ANIMATION = {"KeyedObject": 25, "KeyedProperty": 26, "KeyFrameDouble": 30, "LinearAnimation": 31}
COMMON = {
    "name": (4, "string"), "x": (13, "float"), "y": (14, "float"),
    "rotation": (15, "float"), "scaleX": (16, "float"), "scaleY": (17, "float"),
    "opacity": (18, "float"),
}
GEOMETRY = {
    **COMMON, "width": (20, "float"), "height": (21, "float"), "cornerRadiusTL": (31, "float"),
}
SCHEMA = {
    "Artboard": {"name": (4, "string"), "width": (7, "float"), "height": (8, "float")},
    "Node": COMMON,
    "Shape": COMMON,
    "Ellipse": GEOMETRY,
    "Rectangle": GEOMETRY,
    "SolidColor": {"colorValue": (37, "color")},
    "Fill": {},
    "Stroke": {"thickness": (47, "float")},
    "LinearAnimation": {"name": (55, "string"), "fps": (56, "int"), "duration": (57, "int")},
    "KeyedObject": {"objectId": (51, "reference")},
    "KeyedProperty": {"propertyKey": (53, "int")},
    "KeyFrameDouble": {"frame": (67, "int"), "interpolationType": (68, "interpolation"), "value": (70, "float")},
}


def varuint(value):
    if value < 0:
        raise ValueError("Expected an unsigned integer")
    result = bytearray()
    while value >= 128:
        result.append(128 | (value & 127))
        value >>= 7
    result.append(value)
    return result


def compile_artboard(artboard):
    # Magic, major/minor version, file ID, empty baseline property table.
    data = bytearray(b"RIVE\x07\x00\x00\x00")
    # Empty backboard. The artboard itself occupies component index zero.
    data.extend(b"\x17\x00")
    ids = {}
    next_index = 1

    def value_bytes(kind, value):
        if kind == "string":
            encoded = value.encode()
            return varuint(len(encoded)) + encoded
        if kind == "float":
            return struct.pack("<f", float(value))
        if kind == "color":
            return struct.pack("<I", int(value, 16))
        if kind == "reference":
            return varuint(ids[value])
        if kind == "interpolation":
            return varuint({"hold": 0, "linear": 1}[value])
        return varuint(int(value))

    def emit(element, type_key, parent=None):
        data.extend(varuint(type_key))
        if parent is not None:
            data.extend(varuint(5))
            data.extend(varuint(parent))
        for name, value in element.attrib.items():
            if name == "id":
                continue
            key, kind = SCHEMA[element.tag][name]
            data.extend(varuint(key))
            data.extend(value_bytes(kind, value))
        data.append(0)

    def component(element, parent):
        nonlocal next_index
        index = next_index
        next_index += 1
        if "id" in element.attrib:
            ids[element.attrib["id"]] = index
        emit(element, COMPONENTS[element.tag], parent)
        for child in element:
            component(child, index)

    def animation(element):
        emit(element, ANIMATION[element.tag])
        for child in element:
            animation(child)

    emit(artboard, 1)
    for element in artboard:
        if element.tag in COMPONENTS:
            component(element, 0)
    for element in artboard.findall("LinearAnimation"):
        animation(element)
    return data


if __name__ == "__main__":
    source = Path(__file__).resolve().parent
    artboard = XML.parse(source / "scene.rml").getroot().find("Artboard")
    if artboard is None:
        raise ValueError("Missing Arrival passes artboard")
    target = source.parents[1] / "public" / "arrival.riv"
    target.write_bytes(compile_artboard(artboard))
