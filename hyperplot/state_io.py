import base64
import gzip
import json
import xml.etree.ElementTree as ET


SVG_STATE_NODE = "hyperplot_state"
SVG_STATE_ENCODING = "base64+gzip+json"
SVG_STATE_VERSION = 1
PNG_STATE_KEY = "HyperPlotState"


def xml_local_name(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def encode_state(state):
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    return base64.b64encode(gzip.compress(payload.encode("utf-8"))).decode("ascii")


def decode_state(encoded_state):
    payload = gzip.decompress(base64.b64decode(encoded_state)).decode("utf-8")
    return json.loads(payload)


def svg_namespace(root):
    if root.tag.startswith("{"):
        return root.tag[1:].split("}", 1)[0]
    return ""


def write_svg_state(svg_path, state):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    namespace = svg_namespace(root)
    if namespace:
        ET.register_namespace("", namespace)

    metadata = next(
        (
            child
            for child in list(root)
            if xml_local_name(child.tag) == "metadata"
        ),
        None,
    )
    if metadata is None:
        metadata_tag = f"{{{namespace}}}metadata" if namespace else "metadata"
        metadata = ET.Element(metadata_tag)
        root.insert(0, metadata)

    for child in list(metadata):
        if xml_local_name(child.tag) == SVG_STATE_NODE:
            metadata.remove(child)

    state_node = ET.Element(
        SVG_STATE_NODE,
        {"version": str(SVG_STATE_VERSION), "encoding": SVG_STATE_ENCODING},
    )
    state_node.text = encode_state(state)
    metadata.append(state_node)
    tree.write(svg_path, encoding="utf-8", xml_declaration=True)


def read_svg_state(svg_path):
    tree = ET.parse(svg_path)
    state_node = next(
        (
            element
            for element in tree.getroot().iter()
            if xml_local_name(element.tag) == SVG_STATE_NODE
        ),
        None,
    )
    if state_node is None or not state_node.text:
        raise ValueError(f"{svg_path} does not contain HyperPlot state.")
    return decode_state(state_node.text.strip())


def png_metadata(state):
    return {
        PNG_STATE_KEY: encode_state(state),
        "HyperPlotStateEncoding": SVG_STATE_ENCODING,
        "HyperPlotStateVersion": str(SVG_STATE_VERSION),
    }


def read_png_state(png_path):
    from PIL import Image

    with Image.open(png_path) as image:
        encoded_state = image.info.get(PNG_STATE_KEY)

    if not encoded_state:
        raise ValueError(f"{png_path} does not contain HyperPlot state.")
    return decode_state(encoded_state.strip())
