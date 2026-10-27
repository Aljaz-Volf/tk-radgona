from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.services.uploads import delete_image, save_image


def _image_upload(filename="court.png"):
    stream = BytesIO()
    Image.new("RGB", (24, 16), color=(190, 74, 43)).save(stream, "PNG")
    stream.seek(0)
    return FileStorage(stream=stream, filename=filename, content_type="image/png")


def test_local_image_is_validated_saved_and_deleted(app):
    with app.app_context():
        key, width, height = save_image(_image_upload(), "galleries/1")
        path = Path(app.config["UPLOAD_FOLDER"]) / key
        assert (width, height) == (24, 16)
        assert path.is_file()
        delete_image(key)
        assert not path.exists()


def test_invalid_image_is_rejected(app):
    with app.app_context(), pytest.raises(ValueError):
        save_image(FileStorage(stream=BytesIO(b"not an image"), filename="fake.png"), "news")
