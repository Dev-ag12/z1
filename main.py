import io
import os
import tempfile
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from PIL import Image
import tweepy
import uvicorn
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Set your Twitter credentials here or via environment variables
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

print(TWITTER_API_KEY)
print(TWITTER_API_SECRET)
print(TWITTER_ACCESS_TOKEN)
print(TWITTER_ACCESS_TOKEN_SECRET)
def post_images_to_twitter(image_buffers):
    """
    Uploads the provided image buffers as media to Twitter and posts a tweet.
    This function uses your preset credentials so that tweets are always posted
    from your own Twitter account.
    """
    logger.info("Starting Twitter authentication...")
    auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    logger.info("Twitter authentication successful.")

    media_ids = []
    for idx, img_buffer in enumerate(image_buffers):
        logger.debug(f"Processing image {idx + 1} for upload.")
        img_buffer.seek(0)
        # Use a temporary file to store the image data
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_file.write(img_buffer.read())
            temp_filename = temp_file.name
            logger.debug(f"Temporary file created: {temp_filename}")

        try:
            logger.info(f"Uploading image {idx + 1} to Twitter...")
            media = api.media_upload(temp_filename)
            media_ids.append(media.media_id)
            logger.info(f"Image {idx + 1} uploaded successfully with media_id: {media.media_id}")
        except Exception as e:
            logger.error(f"Error uploading image {idx + 1}: {e}")
            os.remove(temp_filename)
            raise Exception(f"Error uploading image: {e}")
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                logger.debug(f"Temporary file deleted: {temp_filename}")

    try:
        logger.info("Posting tweet with uploaded images...")
        tweet = api.update_status(status="Resized images uploaded", media_ids=media_ids)
        logger.info(f"Tweet posted successfully with tweet id: {tweet.id_str}")
    except Exception as e:
        logger.error(f"Error posting tweet: {e}")
        raise Exception(f"Error posting tweet: {e}")
    return tweet

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
    logger.info("Rendering the upload form.")
    html_content = """
    <html>
      <head>
        <title>Image Upload and Resize</title>
      </head>
      <body>
        <h1>Upload an Image</h1>
        <form action="/upload/" enctype="multipart/form-data" method="post">
          <input name="file" type="file" accept="image/png, image/jpeg">
          <br><br>
          <input type="submit" value="Upload and Process">
        </form>
      </body>
    </html>
    """
    return html_content

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    logger.info("Received an image upload request.")
    # Validate file type
    if file.content_type not in ["image/jpeg", "image/png"]:
        logger.error(f"Unsupported file type received: {file.content_type}")
        raise HTTPException(status_code=400, detail="Unsupported file type. Only JPEG and PNG are allowed.")

    contents = await file.read()
    logger.debug("File content read successfully.")

    try:
        image = Image.open(io.BytesIO(contents))
        logger.info("Image file opened successfully.")
    except Exception as e:
        logger.error(f"Invalid image file: {e}")
        raise HTTPException(status_code=400, detail="Invalid image file.")

    # Define the preset sizes for resizing
    sizes = [(300, 250), (728, 90), (160, 600), (300, 600)]
    image_buffers = []

    for size in sizes:
        logger.info(f"Resizing image to size: {size}")
        resized_img = resize_image(image, size)
        # Convert image to RGB if necessary
        if resized_img.mode != "RGB":
            logger.debug(f"Converting image mode from {resized_img.mode} to RGB for JPEG compatibility.")
            resized_img = resized_img.convert("RGB")
        buf = io.BytesIO()
        resized_img.save(buf, format="JPEG")
        buf.seek(0)
        image_buffers.append(buf)
        logger.debug(f"Image resized to {size} and saved to buffer.")

    try:
        logger.info("Starting to post images to Twitter.")
        tweet = post_images_to_twitter(image_buffers)
    except Exception as e:
        logger.error(f"Error during Twitter posting process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    logger.info("Image upload, resizing, and Twitter post completed successfully.")
    return {"message": "Image uploaded, resized, and posted to Twitter", "tweet_id": tweet.id_str}

if __name__ == "__main__":
    logger.info("Starting FastAPI application...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
