import io
import os
import uuid
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
import uvicorn

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Ensure a static directory exists to serve uploaded images
STATIC_DIR = "static"
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
    logger.info(f"Created directory: {STATIC_DIR}")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def resize_image(image: Image.Image, size: tuple) -> Image.Image:
    """
    Resizes the given image to the specified size using a high-quality Lanczos filter.
    """
    logger.debug(f"Resizing image to {size}...")
    resized = image.resize(size, resample=Image.Resampling.LANCZOS)
    logger.debug("Image resized successfully.")
    return resized

@app.get("/", response_class=HTMLResponse)
async def index():
    """
    Render the image upload form.
    """
    logger.info("Rendering the upload form.")
    html_content = """
    <html>
      <head>
        <title>Image Upload and Resize</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f4f4; }
            .container { max-width: 600px; margin: auto; background: #fff; padding: 20px; border-radius: 8px;
                         box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Upload an Image</h1>
          <form action="/upload/" enctype="multipart/form-data" method="post">
            <input name="file" type="file" accept="image/png, image/jpeg">
            <br><br>
            <input type="submit" value="Upload and Process">
          </form>
        </div>
      </body>
    </html>
    """
    return html_content

@app.post("/upload/", response_class=HTMLResponse)
async def upload_image(file: UploadFile = File(...), request: Request = None):
    """
    Handle image upload, resize the image, save it to the static directory, and
    return an HTML page with a button to open Twitter's tweet composer pre-populated
    with text and the link to the resized image.
    """
    logger.info("Received an image upload request.")
    if file.content_type not in ["image/jpeg", "image/png"]:
        logger.error(f"Unsupported file type received: {file.content_type}")
        raise HTTPException(status_code=400, detail="Unsupported file type. Only JPEG and PNG are allowed.")

    # Read and open the uploaded image
    contents = await file.read()
    try:
        image = Image.open(io.BytesIO(contents))
        logger.info("Image file opened successfully.")
    except Exception as e:
        logger.error(f"Invalid image file: {e}")
        raise HTTPException(status_code=400, detail="Invalid image file.")

    # Choose a preset size (e.g. 300x250) for the resized image
    target_size = (300, 250)
    resized_img = resize_image(image, target_size)
    
    # Ensure image is in RGB mode for JPEG compatibility
    if resized_img.mode != "RGB":
        logger.debug(f"Converting image mode from {resized_img.mode} to RGB for JPEG compatibility.")
        resized_img = resized_img.convert("RGB")

    # Save the resized image in the static folder with a unique filename
    unique_filename = f"{uuid.uuid4()}.jpg"
    save_path = os.path.join(STATIC_DIR, unique_filename)
    resized_img.save(save_path, format="JPEG")
    logger.info(f"Resized image saved at {save_path}")

    # Build the absolute URL for the saved image using request.base_url
    image_url = f"{request.base_url}static/{unique_filename}"
    logger.debug(f"Image URL: {image_url}")

    # Build the Twitter intent URL with a pre-filled tweet text and the image URL
    tweet_text = "Check out this awesome image!"
    twitter_intent_url = (
        f"https://twitter.com/intent/tweet?text={tweet_text.replace(' ', '+')}&url={image_url}"
    )
    logger.info("Constructed Twitter intent URL.")

    # Return an HTML page with a button linking to Twitter's tweet composer
    html_response = f"""
    <html>
      <head>
        <title>Image Uploaded</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                background-color: #f4f4f4;
            }}
            .container {{
                max-width: 600px;
                margin: auto;
                background: #fff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .button {{
                background-color: #1DA1F2;
                color: white;
                border: none;
                padding: 15px 25px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 16px;
                cursor: pointer;
                border-radius: 5px;
            }}
            .button:hover {{
                background-color: #0d95e8;
            }}
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Image Uploaded and Processed</h1>
          <p>Your image has been resized. Click the button below to post it on Twitter:</p>
          <a href="{twitter_intent_url}" target="_blank" class="button">Post to Twitter</a>
          <p>Or view your image <a href="{image_url}" target="_blank">here</a>.</p>
        </div>
      </body>
    </html>
    """
    return html_response

if __name__ == "__main__":
    logger.info("Starting FastAPI application...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
