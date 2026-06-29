"""Logo & header image upload with backend auto-resize/convert."""
import io

import pytest

PIL = pytest.importorskip("PIL")          # skip if Pillow isn't installed
from PIL import Image                       # noqa: E402


@pytest.fixture
def upload_dir(app, tmp_path):
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")
    return app.config["UPLOAD_DIR"]


def _img(w, h, fmt):
    b = io.BytesIO()
    Image.new("RGB", (w, h), (100, 120, 200)).save(b, fmt)
    b.seek(0)
    return b


def _post(auth, kind, fileobj, name):
    return auth.post("/upload/image",
                     data={"kind": kind, "file": (fileobj, name)},
                     content_type="multipart/form-data")


def _open(app, url):
    import os
    rel = url.split("/uploads/")[1]                  # "<account>/<file>"
    return Image.open(os.path.join(app.config["UPLOAD_DIR"], rel))


def test_logo_fits_within_box(auth, app, upload_dir):
    j = _post(auth, "logo", _img(2000, 2000, "PNG"), "big.png").get_json()
    assert "Full image kept" in j["note"]
    im = _open(app, j["url"])
    assert im.width <= 300 and im.height <= 100      # letterboxed inside 300x100
    assert j["url"].endswith(".png")                 # converted to PNG


def test_header_keeps_full_image_without_cropping(auth, app, upload_dir):
    # A 3000x500 banner (6:1) must keep its full content: scaled to width 1200
    # with the aspect ratio preserved (no cover-crop to a forced 3:1 box).
    j = _post(auth, "header", _img(3000, 500, "JPEG"), "wide.jpg").get_json()
    im = _open(app, j["url"])
    assert im.width == 1200                          # width capped at 1200
    assert im.height == 200                          # 6:1 ratio preserved (not 400)
    assert j["url"].endswith(".jpg")


def test_logo_rejects_unsupported_type(auth, upload_dir):
    r = _post(auth, "logo", _img(100, 100, "WEBP"), "x.webp")   # webp not allowed for logo
    assert r.status_code == 400


def test_svg_logo_is_kept_as_is(auth, upload_dir):
    j = _post(auth, "logo", io.BytesIO(b"<svg xmlns='..'/>"), "l.svg").get_json()
    assert j["url"].endswith(".svg")
    assert "SVG" in j["note"]
