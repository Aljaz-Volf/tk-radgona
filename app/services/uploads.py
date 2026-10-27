import secrets
from pathlib import Path

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename


ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=current_app.config["S3_REGION"],
        endpoint_url=current_app.config.get("S3_ENDPOINT_URL") or None,
        aws_access_key_id=current_app.config.get("S3_ACCESS_KEY_ID") or None,
        aws_secret_access_key=current_app.config.get("S3_SECRET_ACCESS_KEY") or None,
    )


def save_image(file_storage, folder: str) -> tuple[str, int, int]:
    if not file_storage or not file_storage.filename:
        raise ValueError("Slika ni bila izbrana.")
    try:
        image = Image.open(file_storage.stream)
        image.verify()
        file_storage.stream.seek(0)
        image = Image.open(file_storage.stream)
        width, height = image.size
        extension = ALLOWED_FORMATS.get(image.format)
    except (UnidentifiedImageError, OSError):
        raise ValueError("Datoteka ni veljavna slika.")
    if not extension:
        raise ValueError("Podprte so slike JPG, PNG in WebP.")
    safe_stem = Path(secure_filename(file_storage.filename)).stem[:60] or "slika"
    key = f"{folder}/{safe_stem}-{secrets.token_hex(8)}{extension}"
    file_storage.stream.seek(0)
    if current_app.config["STORAGE_BACKEND"] == "s3":
        bucket = current_app.config.get("S3_BUCKET")
        if not bucket:
            raise RuntimeError("S3_BUCKET must be configured when STORAGE_BACKEND=s3.")
        content_types = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
        _s3_client().upload_fileobj(
            file_storage.stream,
            bucket,
            key,
            ExtraArgs={"ContentType": content_types[extension]},
        )
    else:
        destination = Path(current_app.config["UPLOAD_FOLDER"]) / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_storage.save(destination)
    return key.replace("\\", "/"), width, height


def delete_image(key: str) -> None:
    if current_app.config["STORAGE_BACKEND"] == "s3":
        bucket = current_app.config.get("S3_BUCKET")
        if bucket:
            _s3_client().delete_object(Bucket=bucket, Key=key)
        return
    upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    target = (upload_root / key).resolve()
    if upload_root in target.parents and target.is_file():
        target.unlink()


def media_url(key: str) -> str:
    public_base = (current_app.config.get("S3_PUBLIC_BASE_URL") or "").rstrip("/")
    if public_base:
        from urllib.parse import quote

        return f"{public_base}/{quote(key)}"
    bucket = current_app.config.get("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET must be configured when STORAGE_BACKEND=s3.")
    return _s3_client().generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=300
    )

