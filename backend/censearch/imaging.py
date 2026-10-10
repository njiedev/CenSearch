"""One bounded EXIF-aware decoder for uploads and fetched images."""

from io import BytesIO
import warnings
import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PIXELS = 24_000_000


def decode(payload: bytes) -> np.ndarray:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as source:
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("Image exceeds 24 megapixel limit")
                image = ImageOps.exif_transpose(source).convert("RGB")
                return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    except (
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ValueError("Not a decodable image, or image is too large") from error
