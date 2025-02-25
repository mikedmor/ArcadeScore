import os
import cv2
import requests
from PIL import Image
from io import BytesIO

# Compression resolution settings
COMPRESSION_RESOLUTIONS = {
    "original": None,  # No compression
    "low": (1920, 1080),
    "medium": (1280, 720),
    "high": (640, 360),
}

def save_image(image_data, filename, storage_path, db_path, compression_level="original"):
    """Saves raw image bytes to a file, resizing large images while keeping PNG format."""
    try:
        # Ensure filename has a .png extension
        filename = filename.rsplit(".", 1)[0] + ".png"

        # Load image from raw bytes
        image = Image.open(BytesIO(image_data)).convert("RGBA")  # Ensure PNG compatibility

        # Determine the maximum size based on compression level
        max_size = COMPRESSION_RESOLUTIONS.get(compression_level)
        print(f"Compressing image to {compression_level}: {max_size}")

        # Resize image if it exceeds max dimensions
        if max_size and (image.width > max_size[0] or image.height > max_size[1]):
            print(f"Resizing image from {image.size} to fit {max_size}...")
            image.thumbnail(max_size)  # Uses anti-aliasing by default in newer versions of Pillow

        # Save optimized PNG
        full_filepath = os.path.join(storage_path, filename)
        relative_filepath = os.path.join(db_path, filename).replace("\\", "/")

        image.save(full_filepath, format="PNG", optimize=True, compress_level=3)

        print(f"Image saved successfully: {relative_filepath}")
        return relative_filepath  # Store this in DB

    except Exception as e:
        print(f"Failed to save image: {e}")
        return None

def extract_first_frame(video_url, output_filename, storage_path, db_path, rotate=False, compression_level="original"):
    """Extracts the first frame from an MP4 video, optionally rotates it, and saves it as an image."""
    try:
        print(f"Downloading video from: {video_url}")

        response = requests.get(video_url, stream=True)
        if response.status_code != 200:
            print(f"❌ Failed to download video. HTTP Status: {response.status_code}")
            return None

        temp_file = "temp_video.mp4"
        with open(temp_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print("Video downloaded successfully. Attempting to open with OpenCV...")

        cap = cv2.VideoCapture(temp_file)
        if not cap.isOpened():
            print("❌ OpenCV failed to open video.")
            return None

        success, frame = cap.read()
        cap.release()

        if not success or frame is None:
            print("❌ Failed to extract a valid frame from the video.")
            return None

        print("Frame extracted successfully.")

        # Convert OpenCV frame (BGR) to PIL Image (RGB)
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        if rotate:
            print("Rotating image 90 degrees clockwise...")
            image = image.rotate(-90, expand=True)  # Rotate clockwise

        # Convert image to raw PNG bytes
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True, compress_level=3)
        raw_image_data = buffer.getvalue()

        print(f"Saving extracted frame as PNG: {output_filename}")
        saved_path = save_image(raw_image_data, output_filename, storage_path, db_path, compression_level)

        if saved_path:
            print(f"Image successfully saved: {saved_path}")
        else:
            print("❌ Image saving failed.")

        return saved_path

    except Exception as e:
        print(f"❌ Error extracting frame from {video_url}: {e}")
        return None
    
def rotate_image_90(image_data, output_filename, storage_path, db_path, compression_level="original"):
    """Rotates an image 90 degrees clockwise and saves it."""
    try:
        image = Image.open(BytesIO(image_data))
        rotated_image = image.rotate(-90, expand=True)

        buffer = BytesIO()
        rotated_image.save(buffer, format="PNG")
        return save_image(buffer.getvalue(), output_filename, storage_path, db_path, compression_level)
    except Exception as e:
        print(f"Failed to rotate image: {e}")
        return None
