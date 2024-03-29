from flask import Flask, request, make_response, jsonify, send_file, url_for, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from urllib.parse import unquote
from fake_useragent import UserAgent

import requests
import time
from rembg import remove, new_session

from io import BytesIO
from PIL import Image

import os

from functions.write_to_logs import write_to_logs


app = Flask(__name__)

limiter = Limiter(key_func=get_remote_address, app=app, default_limits=[])

CORS(app)


@app.route("/")
@limiter.exempt
def hello():
    return "API is working!"


@app.route("/share/<cid>")
@limiter.exempt
def share(cid):
    return (
        '<html><head><meta name="twitter:card" content="summary_large_image" /><meta property="og:url" content="https://'
        + cid
        + '.ipfs.nftstorage.link" /><meta property="og:title" content="Kwentize yourself" /><meta property="og:description" content="Kwentize yourself with our tool." /><meta property="og:image" content="https://'
        + cid
        + '.ipfs.nftstorage.link" /></head><body>redirecting to image..</body><script>setTimeout(function(){ window.location.href = "https://'
        + cid
        + '.ipfs.nftstorage.link"; }, 200)</script></html>'
    )


@app.route("/remove", methods=["POST", "OPTIONS"])
@limiter.exempt
def remove_bg():
    content_type = request.headers.get("Content-Type")
    if content_type == "application/json":
        json_data = request.json
        now = str(time.time())
        url = json_data["url"]
        data = requests.get(url).content
        file_extension = url.split(".")[-1]  # Extract file extension from URL
        input_path = f"./origin/{now}.{file_extension}"

        # Save the downloaded image
        with open(input_path, "wb") as f:
            f.write(data)

        output_path = f"./static/{now}.png"  # Output always as PNG

        res = {}
        res["result"] = f"{now}.png"

        with open(input_path, "rb") as i:
            with open(output_path, "wb") as o:
                input_data = i.read()
                model_name = "u2net_human_seg"
                session = new_session(model_name)
                output = remove(input_data, session=session)
                o.write(output)

        # Delete the input file after processing
        os.remove(input_path)

        return jsonify(res)
    else:
        return "Content-Type not supported!"



def extract_params():
    if request.method == "POST":
        if request.is_json:
            data = request.json
            address = data.get("custody_address")
            username = data.get("username")
            pfp_url = data.get("pfp_url")
        else:
            address_encoded = request.args.get("custody_address")
            username_encoded = request.args.get("username")
            pfp_url_encoded = request.args.get("pfp_url")
            address = unquote(address_encoded)
            username = unquote(username_encoded)
            pfp_url = unquote(pfp_url_encoded)
    else:
        return jsonify({"error": "Invalid request method"}), 400

    return address, username, pfp_url


@app.route("/remove_and_overlay", methods=["POST"])
def remove_and_overlay():
    # @limiter.limit("4 per day", key_func=lambda: request.json["username"])
    try:
        
        address, username, pfp_url = extract_params()

        print("Address:", address)
        print("Username:", username)
        print("PFP URL:", pfp_url)

        if not (username and address):
            return jsonify({"error": "Username and address must be provided"}), 400

        now = str(time.time())


        # Fetch existing files in the static directory
        static_folder_path = os.path.join(os.getcwd(), 'static')
        existing_files = os.listdir(static_folder_path)
        # Filter files matching the username and address
        matching_files = [file for file in existing_files if file.startswith(f"{username}_{address}")]

        # Calculate the next file number
        next_file_number = len(matching_files)
        # Format the file number with leading zeros
        formatted_file_number = f"{next_file_number:04d}"
        # Construct the next filename
        next_filename = f"{username}_{address}_{formatted_file_number}.png"
   
        file_extension = "png"
        input_path = f"./origin/{now}.{file_extension}"
        output_path = f"./static/{next_filename}"  # Output always as PNG

        print("Input Path:", input_path)
        print("Output Path:", output_path)

        # try:
        #     response = requests.get(pfp_url)
        #     response.raise_for_status()  # Raise an error for bad status codes
        #     data = response.content
        # except requests.exceptions.RequestException as e:
        #     print("Error fetching image:", e)
        try:

            data = fetch_image(pfp_url)
        except Exception as e:
            print("Error fetching image:", e)

        print("Data Length:", len(data))

        try:
            background_image_filename = f"background_{now}.{file_extension}"
            background_image_path = os.path.join("static", background_image_filename)
            with open(background_image_path, "wb") as f:
                f.write(data)

            # Remove background from the provided image
            background_removed_image_bytes = remove_background_using_API(data)
        except Exception as e:
            print("Error saving image:", e)


        if background_removed_image_bytes is None:
            return jsonify({"error": "Failed to remove background from image"}), 500

        # Overlay the background removed image on top of a background
        result_image_bytes = overlay_images(background_removed_image_bytes)
        os.remove(background_image_path)

        with open(output_path, "wb") as f:
            f.write(result_image_bytes)

        if result_image_bytes is None:
            return jsonify({"error": "Failed to overlay images"}), 500

        # # Return the resulting image as a response
        # return send_file(BytesIO(result_image_bytes), mimetype='image/png')

        # Write to logs
        write_to_logs(address, username, pfp_url, output_path)

        # Return the filename of the resulting image
        return jsonify({"filename": output_path})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def fetch_image(webpage_url):
    # Create a fake user agent
    user_agent = UserAgent().random

    # Set headers to simulate a web browser
    headers = {'User-Agent': user_agent}

    # Send a GET request to the URL with headers
    response = requests.get(webpage_url, headers=headers)

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Save the content of the response (the image) to a file
        print("Image downloaded successfully.")
        return response.content

    else:
        print("Failed to download the image. Status code:", response.status_code)




@app.route("/download_file", methods=["POST"])
def download_file():
    print("tried to download")
    try:
        # Get the username from the POST request data
        username_encoded = request.args.get("username")
        username = unquote(username_encoded)

        # Check if the username exists
        if username:
            # Get the static folder path
            static_folder_path = os.path.join(os.getcwd(), 'static')

         # Find files starting with the username
            matching_files = [file for file in os.listdir(static_folder_path) if file.startswith(username + '_')]

            # Sort the files by modification time
            sorted_files = sorted(matching_files, key=lambda x: os.path.getmtime(os.path.join(static_folder_path, x)), reverse=True)

            # Check if any files matched the criteria
            if sorted_files:
                # Get the latest file
                latest_file = sorted_files[0]

                # Construct the URL to the file
                file_url = url_for('static', filename=latest_file)

                # Return the file for download
                # return send_file(file_path, as_attachment=True)
            
                # Construct HTML content with frame metadata
                html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta property="fc:frame" content="vNext" />
                        <meta property="fc:frame:image" content="http://3.21.66.28/static/{file_path}" />
                        <meta property="fc:frame:post_url" content="http://3.21.66.28/static/" />
                    </head>
                    </html>
                """

                # Return the HTML content as the response
                return html_content




            else:
                return jsonify({"error": f"No files found for username '{username}'"}), 404
        else:
            return jsonify({"error": "Username not provided"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def remove_background_from_image(foreground_image_bytes):
    try:
        # Prepare data for removing background
        now = str(time.time())
        input_path = "./origin/" + now + ".png"
        output_path = "./static/" + now + ".png"

        # Write the provided foreground image bytes to a file
        with open(input_path, "wb") as f:
            f.write(foreground_image_bytes)

        # Remove background from the image
        with open(input_path, "rb") as i:
            with open(output_path, "wb") as o:
                input_image_bytes = i.read()
                model_name = "u2net_human_seg"
                session = new_session(model_name)
                output_image_bytes = remove(input_image_bytes, session=session)
                o.write(output_image_bytes)
        
        # Delete the input file after processing
        os.remove(input_path)

        # Read the resulting image bytes
        with open(output_path, "rb") as f:
            result_image_bytes = f.read()

        os.remove(output_path)

        return result_image_bytes

    except Exception as e:
        print(f"Removebg Error: {e}")
        return None
    
def remove_background_using_API(foreground_image_bytes):
    try:
        # API endpoint for removing background
        api_endpoint = "https://api.removebg.com/v1.0/removebg"

        data = {"size": "auto"} 

        # Prepare headers with API key
        headers = {
            'X-Api-Key': "N7ofK6rsQTtk3oKPbpDM3dV3",
        }

        # Make API request to remove background
        response = requests.post(api_endpoint,
                                data = data,
                                headers=headers,
                                files={'image_file': ('image.png', foreground_image_bytes)})

        # Check if request was successful
        if response.status_code == 200:
            return response.content  # Return the resulting image bytes
        else:
            print(f"Failed to remove background. Status code: {response.status_code}")
            return None

    except Exception as e:
        print(f"Error occurred while removing background: {e}")
        return None

def overlay_images(foreground_image_bytes, background_path="assets/frame_img.png", mask_path="assets/mask.png"):
    try:
        # Open the background image
        background = Image.open(background_path)

        # # Open the mask image
        # mask = Image.open(mask_path)

        # # Convert mask to RGBA if it doesn't have alpha channel
        # if mask.mode != 'RGBA':
        #     mask = mask.convert('RGBA')

        # Open the foreground image from bytes
        foreground = Image.open(BytesIO(foreground_image_bytes))

        # Convert foreground to RGBA if it doesn't have alpha channel
        if foreground.mode != 'RGBA':
            foreground = foreground.convert('RGBA')

        # Calculate the minimum and maximum height for the foreground image
        min_height = int(background.height * 0.8)
        min_width = int(background.width * 0.8)

        # Calculate the maximum width to maintain the aspect ratio
        max_width = int((foreground.width / foreground.height) * min_height)

        # Ensure the resized width does not exceed the background width
        max_width = min(max_width, background.width)

        # Resize foreground image while maintaining aspect ratio and fitting within limits
        foreground.thumbnail((max_width, min_height))

        # Check if the foreground image is smaller than desired
        if foreground.width < min_width or foreground.height < min_height:
            # Calculate new dimensions to make the foreground image bigger
            target_width = min(max_width, min_width)
            target_height = min(min_height, int((foreground.height / foreground.width) * target_width))
            foreground = foreground.resize((target_width, target_height))

 

        # Calculate position to place the foreground image at the center of background
        x = (background.width - foreground.width) // 2
        y = (background.height - foreground.height) // 2

        # Paste the foreground image onto the background
        background.paste(foreground, (x, y), foreground)

        #use PIL and overlay the image frame_img_bottom.png on top of background
        kwenta_bottom = Image.open("assets/frame_img_bottom.png")
        # Ensure transparency is preserved for kwenta_bottom image
        kwenta_bottom = kwenta_bottom.convert("RGBA")

        background.paste(kwenta_bottom, (0, 0), kwenta_bottom)


        # Return the resulting image bytes
        with BytesIO() as output_buffer:
            background.save(output_buffer, format='PNG')
            return output_buffer.getvalue()

    except Exception as e:
        print(f"overlay_images Error: {e}")
        return None
    
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)
    
@app.route("/remove_and_overlay_test", methods=["POST"])
def remove_and_overlay_test():
    try:
        # address_encoded = request.args.get("custody_address")
        # username_encoded = request.args.get("username")
        # pfp_url_encoded = request.args.get("pfp_url")

        # address = unquote(address_encoded)
        # username = unquote(username_encoded)
        # pfp_url = unquote(pfp_url_encoded)

        data = request.json

        # Extract parameters from the JSON data
        address = data.get("custody_address")
        username = data.get("username")
        pfp_url = data.get("pfp_url")

        print("Address:", address)
        print("Username:", username)
        print("PFP URL:", pfp_url)

        if not (username and address):
            return jsonify({"error": "Username and address must be provided"}), 400

        now = str(time.time())


        # Fetch existing files in the static directory
        static_folder_path = os.path.join(os.getcwd(), 'static')
        existing_files = os.listdir(static_folder_path)
        # Filter files matching the username and address
        matching_files = [file for file in existing_files if file.startswith(f"{username}_{address}")]

        # Calculate the next file number
        next_file_number = len(matching_files)
        # Format the file number with leading zeros
        formatted_file_number = f"{next_file_number:04d}"
        # Construct the next filename
        next_filename = f"{username}_{address}_{formatted_file_number}.png"
   
        file_extension = "png"
        input_path = f"./origin/{now}.{file_extension}"
        output_path = f"./static/{next_filename}"  # Output always as PNG

        print("Input Path:", input_path)
        print("Output Path:", output_path)

        # try:
        #     response = requests.get(pfp_url)
        #     response.raise_for_status()  # Raise an error for bad status codes
        #     data = response.content
        # except requests.exceptions.RequestException as e:
        #     print("Error fetching image:", e)
        try:

            data = fetch_image(pfp_url)
        except Exception as e:
            print("Error fetching image:", e)

        print("Data Length:", len(data))

        try:
            background_image_filename = f"background_{now}.{file_extension}"
            background_image_path = os.path.join("static", background_image_filename)
            with open(background_image_path, "wb") as f:
                f.write(data)

            # Remove background from the provided image
            background_removed_image_bytes = remove_background_using_API(data)
        except Exception as e:
            print("Error saving image:", e)


        if background_removed_image_bytes is None:
            return jsonify({"error": "Failed to remove background from image"}), 500

        # Overlay the background removed image on top of a background
   
        result_image_bytes = overlay_images(background_removed_image_bytes)
        os.remove(background_image_path)

        with open(output_path, "wb") as f:
            f.write(result_image_bytes)

        if result_image_bytes is None:
            return jsonify({"error": "Failed to overlay images"}), 500

        # # Return the resulting image as a response
        # return send_file(BytesIO(result_image_bytes), mimetype='image/png')

        # Return the filename of the resulting image
        return jsonify({"filename": output_path})

    except Exception as e:
        return jsonify({"error": str(e)}), 500