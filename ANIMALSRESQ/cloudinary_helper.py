# cloudinary_helper.py

import cloudinary
import cloudinary.uploader
from config import Config

cloudinary.config(
    cloud_name=Config.CLOUDINARY_CLOUD_NAME,
    api_key=Config.CLOUDINARY_API_KEY,
    api_secret=Config.CLOUDINARY_API_SECRET
)


def upload_image(file):
    result = cloudinary.uploader.upload(file)
    return result.get("secure_url"), result
