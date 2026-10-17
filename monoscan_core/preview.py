"""N7 read-only PLY/OBJ geometry adapters for a Tk Canvas viewport.

Source artifacts are never modified. Mesh faces are rendered as an OPEN
surface. No geometry is synthesized when a model is missing or invalid.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path


class PreviewError(ValueError):
    pass


@dataclass(frozen=True)
class PreviewModel:
    points: tuple[tuple[float, float, float], ...]
    colors: tuple[str, ...]
    faces: tuple[tuple[int, int, int], ...]
    kind: str


def _finite(x):
    n = float(x)
    if not math.isfinite(n):
        raise PreviewError("Nonfinite geometry coordinate")
    return n


def load_ascii_ply(path, *, max_points=6000):
    """Read sample of native ASCII PLY, retaining actual RGB and source points."""
    path = Path(path)
    if not 50 <= max_points <= 20000:
        raise PreviewError("Invalid preview point limit")
    try:
        with path.open("r", encoding="ascii") as file:
            if file.readline().strip() != "ply":
                raise PreviewError("Not a PLY point cloud")
            if file.readline().strip() != "format ascii 1.0":
                raise PreviewError("Only native ASCII PLY is supported")
            count, header_lines = None, 0
            while True:
                line = file.readline()
                header_lines += 1
                if not line or header_lines > 120:
                    raise PreviewError("Malformed PLY header")
                tokens = line.strip().split()
                if tokens[:2] == ["element", "vertex"] and len(tokens) == 3:
                    count = int(tokens[2])
                if tokens and tokens[0] == "end_header":
                    break
            if count is None or not 1 <= count <= 1_000_000:
                raise PreviewError("Missing or oversized PLY vertex collection")
            step = max(1, math.ceil(count / max_points))
            points, colors = [], []
            for i in range(count):
                line = file.readline()
                if not line:
                    raise PreviewError("Truncated PLY vertex collection")
                if i % step:
                    continue
                fields = line.split()
                if len(fields) < 3:
                    raise PreviewError("Malformed PLY XYZ")
                x, y, z = map(_finite, fields[:3])
                points.append((x, y, z))
                if len(fields) >= 6:
                    rgb = [int(a) for a in fields[3:6]]
                    if any(not 0 <= n <= 255 for n in rgb):
                        raise PreviewError("Invalid point RGB")
                    colors.append("#" + "".join(f"{c:02x}" for c in rgb))
                else:
                    colors.append("#55add7")
        return PreviewModel(tuple(points), tuple(colors), (), "points")
    except (OSError, UnicodeError, ValueError, OverflowError) as exc:
        if isinstance(exc, PreviewError):
            raise
        raise PreviewError("Invalid native PLY file") from exc


def load_obj_mesh(path, *, max_vertices=150000, max_faces=3500):
    """Load vertex-indexed *open* mesh and sample real faces for UI rendering."""
    path = Path(path)
    if not 100 <= max_vertices <= 150000 or not 20 <= max_faces <= 30000:
        raise PreviewError("Invalid OBJ preview resource limit")
    try:
        vertices, triangles = [], []
        with path.open("r", encoding="ascii") as stream:
            for row in stream:
                if row.startswith("v "):
                    xyz = row.split()
                    if len(xyz) < 4:
                        raise PreviewError("Malformed OBJ vertex")
                    vertices.append(tuple(_finite(v) for v in xyz[1:4]))
                    if len(vertices) > max_vertices:
                        raise PreviewError("OBJ exceeds bounded UI preview")
                elif row.startswith("f "):
                    fields = row.split()[1:]
                    if len(fields) != 3:
                        raise PreviewError("Only N6 triangular mesh is supported")
                    ids = []
                    for field in fields:
                        raw = field.split("/")[0]
                        i = int(raw)
                        if i <= 0 or i > len(vertices):
                            raise PreviewError("Invalid OBJ face index")
                        ids.append(i-1)
                    if len(set(ids)) < 3:
                        raise PreviewError("Degenerate mesh face")
                    triangles.append(tuple(ids))
                    if len(triangles) > 1_000_000:
                        raise PreviewError("Excessive OBJ face count")
        if not vertices or not triangles:
            raise PreviewError("No connected open mesh geometry")
        stride = max(1, math.ceil(len(triangles) / max_faces))
        sampled = triangles[::stride]
        kept = sorted({i for tri in sampled for i in tri})
        mapping = {old: new for new, old in enumerate(kept)}
        return PreviewModel(tuple(vertices[i] for i in kept),
                            tuple("#7ac7d5" for _ in kept),
                            tuple(tuple(mapping[i] for i in tri) for tri in sampled), "mesh")
    except (OSError, UnicodeError, ValueError, OverflowError) as exc:
        if isinstance(exc, PreviewError):
            raise
        raise PreviewError("Invalid native OBJ mesh") from exc


def geometry_for_run(item, view_kind):
    path = Path(item["path"])
    if view_kind == "mesh":
        if item["kind"] != "dense":
            raise PreviewError("Mesh is available only for N6 dense runs")
        return load_obj_mesh(path / "mesh.obj")
    if view_kind == "dense":
        if item["kind"] != "dense":
            raise PreviewError("Dense cloud is available only for N6 dense runs")
        return load_ascii_ply(path / "dense.ply")
    if view_kind in ("sparse", "refined"):
        if item["kind"] not in ("sparse", "refined"):
            raise PreviewError("Sparse cloud requires an N3/N4/N5 run")
        return load_ascii_ply(path / "sparse.ply")
    raise PreviewError("Unknown visual representation")


def project_preview(points, width, height, *, yaw=0.5, pitch=-0.2, zoom=0.92):
    """Deterministic orthographic projection normalized to existing geometry."""
    if not points:
        raise PreviewError("No geometry to display")
    if min(width, height) <= 0 or not 0.2 <= zoom <= 3:
        raise PreviewError("Invalid projection settings")
    cx = sum(v[0] for v in points) / len(points)
    cy = sum(v[1] for v in points) / len(points)
    cz = sum(v[2] for v in points) / len(points)
    a, b = math.cos(yaw), math.sin(yaw)
    c, d = math.cos(pitch), math.sin(pitch)
    coordinates = []
    for x, y, z in points:
        x, y, z = x-cx, y-cy, z-cz
        horizontal = a*x + b*z
        depth = -b*x + a*z
        vertical = c*y - d*depth
        z_order = d*y + c*depth
        coordinates.append((horizontal, vertical, z_order))
    span_x = max(v[0] for v in coordinates) - min(v[0] for v in coordinates)
    span_y = max(v[1] for v in coordinates) - min(v[1] for v in coordinates)
    scale = 0.80 * min(width, height) * zoom / max(span_x, span_y, 1e-8)
    return [(width/2+x*scale, height/2-y*scale, z) for x, y, z in coordinates]
