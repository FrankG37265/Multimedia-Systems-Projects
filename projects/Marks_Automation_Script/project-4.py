import csv
import xlsxwriter
import argparse
import ffmpeg
import sys
import os
import pymongo
import pandas as pd
import numpy as np
import vimeo
from dotenv import load_dotenv
import time

load_dotenv()

parser = argparse.ArgumentParser(description="A script that something")
parser.add_argument("--baselight", type=str, help="Path to baselight file.")
parser.add_argument("--xytech", type=str, help="Path to xytech file.")
parser.add_argument("--process", type=str, help="Path to video file.")
parser.add_argument("--output", action="store_true", help="Flags to output xlsx file.")
parser.add_argument("--WM", action='store_true', help="Add a watermark to the videos.")
args = parser.parse_args()

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["project4"]
xycol = mydb["xytech"]
blcol = mydb["baselight"]

def upload_to_vimeo(videopath, name):
    access_token = os.getenv("ACCESS_TOKEN")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")

    client = vimeo.VimeoClient(
        token=access_token,
        key=client_id,
        secret=client_secret
    )

    video = videopath
    uri = client.upload(video, data={
        'name': name
    })

    print(f"Video uploaded! URI: {uri}")

    status = client.get(uri + "?fields=transcode.status").json().get("transcode", {}).get("status", "N/A")
    link = client.get(uri + "?fields=link").json().get("link", "N/A")
    title = client.get(uri + "?fields=name").json().get("name", "N/A")

    return [uri, title, link, status]

def render_video(video, name, frames):
    output_file = name
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    startframe = frames.split("-")[0]
    endframe = frames.split("-")[1]

    stream = ffmpeg.input(video)
    stream = stream.filter("select", f"between(n,{startframe},{endframe})")
    stream = ffmpeg.output(stream, output_file)
    ffmpeg.run(stream)
    print(f"\n\nShot rendered and saved as {output_file}\n\n")

def generate_thumbnail(input_file, frame, name="thumbnails/NONAME.png"):
    output_file = name
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    frame_time = frame / 24
    (
        ffmpeg
        .input(input_file, ss=frame_time)
        .filter('scale', 96, 74)
        .output(output_file, vframes=1, format='image2', update=1)
        .overwrite_output()
        .run()
    )
    print(f"\n\nThumbnail generated and saved as {output_file}")

def watermark(input_file, name="videos/NONAME.mp4"):
    output_path = name
    output_file = output_path.split("/")[1] # Remove folder from output file name for watermark text
    (
        ffmpeg
        .input(input_file)
        .drawtext(text=output_file, fontcolor='white', fontsize=24, x="w-text_w-10", y="10")
        .output(output_path, update=1)
        .overwrite_output()
        .run()
    )

def probetimecode(video):
    probe = ffmpeg.probe(video)
    for stream in probe['streams']:
        if 'tags' in stream and 'timecode' in stream ['tags']:
            return stream['tags']['timecode']
        
    if 'tags' in probe['format'] and 'timecode' in probe ['format']['tags']:
        return probe['format']['tags']['timecode']
    
    return -1

def probeframelimit(video):
    try:
        probe = ffmpeg.probe(video)
        videostream = next(
            (stream for stream in probe["streams"] if stream.get("codec_type") == "video"),
            None
        )
        if videostream is None:
            return -1

        framerate = videostream.get("avg_frame_rate", "0/1")
        fpsnum, fpsden = framerate.split("/")
        fpsden = float(fpsden)
        if fpsden == 0:
            return -1

        fps = float(fpsnum) / fpsden
        duration = float(probe["format"]["duration"])
        return max(int(duration * fps) - 1, 0)
    except Exception:
        return -1

def totimecode(frame):
    if frame < 24:
        return f"00:00:00:{frame:02}"
    
    seconds = frame // 24
    frames = frame % 24
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}:{frames:02}"

def toframes(timecode):
    timecodelist = timecode.split(":")
    hours = int(timecodelist[0])
    minutes = int(timecodelist[1])
    seconds = int(timecodelist[2])
    frames = int(timecodelist[3])
    
    minutes += hours * 60
    seconds += minutes * 60
    frames += seconds * 24

    print(f"{timecode} converted to {frames}")
    return frames

def addhandles(framerange):
    startrange, endrange = framerange.split("-")
    startrange = int(startrange)
    endrange = int(endrange)

    if startrange < 48:
        startrange = 0
    else:
        startrange = startrange - 48

    endrange = endrange + 48

    return f"{startrange}-{endrange}"

def setframes(frames):
    result = []
    startrange = 0
    endrange = 0

    for frame in frames:
        if startrange == 0 and endrange == 0:
            startrange = frame
            endrange = frame
            continue
        if int(frame) == int(endrange) +1:
            endrange = frame
            continue
        if startrange == endrange:
            result.append(startrange)
            startrange = frame
            endrange = frame
            continue

        result.append(f"{startrange}-{endrange}")
        startrange = frame
        endrange = frame

    if startrange != 0 and endrange != 0:
        if startrange == endrange:
            result.append(startrange)
        else:
            result.append(f"{startrange}-{endrange}")

    return result

def createbldict(blfile):
    bldict = []
    with open(blfile, "r") as baselight:
        data = baselight.read()
        lines = data.splitlines()

        for line in lines:
            currentpath = line.split(" ")
            currentpath = [item for item in currentpath if item.strip()]
            frameset = setframes(currentpath[1:])

            for frame in frameset:
                record = {"Path": currentpath[0], "Frames": frame}
                bldict.append(record)

    return bldict

def createxydict(xyfile):
    xydict = []
    with open(xyfile, "r") as xytech:
        data = xytech.read()
        lines = data.splitlines()

        if "Workorder" in lines[0]:
            workorder = lines[0].split(" ")[2]

        for line in lines:
            if "/" in line:
                record = {
                    "Workorder": workorder,
                    "Location": line
                }
                xydict.append(record)

    return xydict

def findmarks(framelimit, handles=False):
    xytechfolders = xycol.distinct("Location")
    baselightfolders = list(blcol.find({}, {"_id": 0}))

    #make the output list with the right file paths
    for entry in baselightfolders:
        querypath = entry["Path"].removeprefix("/baselightfilesystem1/")
        for folder in xytechfolders:
            if querypath in folder:
                entry["Path"] = folder

    #remove non ranges
    baselightfolders = [entry for entry in baselightfolders if "-" in entry.get("Frames")]

    # find all ranges within limit and clip any range that crosses the limit
    clippedfolders = []
    for entry in baselightfolders:
        startframe = int(entry.get("Frames").split("-")[0])
        endframe = int(entry.get("Frames").split("-")[1])

        if startframe > framelimit:
            continue
        if endframe > framelimit:
            endframe = framelimit

        entry["Frames"] = f"{startframe}-{endframe}"
        clippedfolders.append(entry)

    baselightfolders = clippedfolders

    # add a timecode version of the frame range
    for entry in baselightfolders:
        startframe = int(entry.get("Frames").split("-")[0])
        endframe = int(entry.get("Frames").split("-")[1])
        starttime = totimecode(startframe)
        endtime = totimecode(endframe)
        entry["Timecode"] = f"{starttime}-{endtime}"
    
    if handles:
        # add handles so easy to access later
        for entry in baselightfolders:
            frames = entry.get("Frames")
            entry["Handles"] = addhandles(frames)

    return baselightfolders

def generateoutput(video, processlist):
    imagepaths = []

    if not processlist:
        print("No frame ranges found within the bounds of the source video.")
        return

    workbook = xlsxwriter.Workbook("CrucibleOutput.xlsx")
    worksheet = workbook.add_worksheet()
    headers = list(processlist[0].keys())

    for index, record in enumerate(processlist):
        frame = int(record.get("Frames").split("-")[0])
        imagepaths.append(f"thumbnails/shot{index}.png")
        generate_thumbnail(video, frame, f"thumbnails/shot{index}.png")

    worksheet.write_row(0, 0, headers)
    for i, entry in enumerate(processlist, start=1):
        worksheet.write_row(i, 0, [entry.get(h) for h in headers])

    worksheet.write(0, 3, "Thumbnail")
    for row_num, image in enumerate(imagepaths, start=1):
        worksheet.insert_image(row_num, 3, image)

    workbook.close()


#main
if args.xytech:
    data = createxydict(args.xytech)
    x = xycol.insert_many(data)
    print(f"Inserted {len(x.inserted_ids)} records from {args.xytech} into MongoDB collection {xycol.name}.")

if args.baselight:
    data = createbldict(args.baselight)
    x = blcol.insert_many(data)
    print(f"Inserted {len(x.inserted_ids)} records from {args.baselight} into MongoDB collection {blcol.name}.")

if args.process:
    framelimit = probeframelimit(args.process)
    if framelimit == -1:
        print("ERROR! Could not determine video frame limit!")
        sys.exit(1)
    marked_data = findmarks(framelimit)

    if args.output:
        generateoutput(args.process, marked_data)
    
    for i, record in enumerate(marked_data):
        frames = record.get("Frames")
        handles = addhandles(frames)
        print(f"\n\n\nFrame Range: {frames} Handles: {handles}\n\n\n")
        render_video(args.process, f"videos/Shot{i}.mp4", handles)
        time.sleep(2)
    
    files = [f"videos/Shot{i}.mp4" for i in range(len(marked_data))]
    csvlist = [["URI", "Title", "Link", "Status"]]

    if args.WM:
        for i, record in enumerate(marked_data):
            watermark(f"videos/Shot{i}.mp4", f"videos/Shot{i}_WM.mp4")
            time.sleep(2)
        files.extend(f"videos/Shot{i}_WM.mp4" for i in range(len(marked_data)))

    for i, file in enumerate(files):
        csvlist.append(upload_to_vimeo(file, file.split("/")[1].split(".")[0]))
        time.sleep(2)
    
    with open("vimeo_uploads.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(csvlist)

