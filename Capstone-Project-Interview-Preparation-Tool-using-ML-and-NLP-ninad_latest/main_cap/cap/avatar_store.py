"""
Profile photos: validate an uploaded image and turn it into a small JPEG.

Every upload is decoded and re-encoded (never stored as sent), which
  * rejects anything that isn't really an image, whatever its name says;
  * strips metadata (EXIF, including GPS location from phone photos);
  * applies the phone's rotation flag, so photos aren't sideways;
  * crops to a centred square and scales to AVATAR_SIZE px, ~10-30 KB.
The result is stored on the users row (models.User.avatar).
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

AVATAR_SIZE = 256
MAX_AVATAR_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000               # refuse "decompression bomb" images before decoding them
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
BACKGROUND = (26, 26, 26)             # fills transparent areas (the UI is dark)


class AvatarError(ValueError):
    """The upload can't be used as a profile photo; the message is safe to show."""


def process_avatar(file) -> bytes:
    """A werkzeug FileStorage (or any object with .read()) -> JPEG bytes."""
    if file is None or not getattr(file, "filename", "x"):
        raise AvatarError("Please choose an image.")
    data = file.read(MAX_AVATAR_BYTES + 1)
    if not data:
        raise AvatarError("The image is empty.")
    if len(data) > MAX_AVATAR_BYTES:
        raise AvatarError("Image is too large (maximum 5 MB).")
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ALLOWED_FORMATS:
                raise AvatarError("Please upload a JPG, PNG, WEBP or GIF image.")
            if img.width * img.height > MAX_PIXELS:
                raise AvatarError("Image dimensions are too large.")
            img.seek(0)                                  # first frame of an animated GIF
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                flat = Image.new("RGB", img.size, BACKGROUND)
                flat.paste(img, mask=img.getchannel("A"))
                img = flat
            else:
                img = img.convert("RGB")
            img = ImageOps.fit(img, (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            img.save(out, "JPEG", quality=85, optimize=True)
            return out.getvalue()
    except AvatarError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise AvatarError("That file isn't a readable image.")
