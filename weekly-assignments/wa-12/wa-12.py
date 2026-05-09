import vimeo
import os
from dotenv import load_dotenv

load_dotenv()

accesstoken = os.getenv("ACCESS_TOKEN")
clientkey = os.getenv("CLIENT_ID")
clientsecret = os.getenv("CLIENT_SECRET")

client = vimeo.VimeoClient(
    token=accesstoken,
    key=clientkey,
    secret=clientsecret
)

video = "snow.MP4"
uri = client.upload(video, data={
    'name': 'Weekly Assignment 12',
    'description': 'Uploaded through python for weekly assignment 12.'
})

print(f"Video uploaded! URI: {uri}")