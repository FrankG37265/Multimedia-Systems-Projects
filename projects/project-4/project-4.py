import csv
import argparse
import ffmpeg
import sys
import os
import pymongo
import pandas as pd
import numpy as np

parser = argparse.ArgumentParser(description="A script that something")
parser.add_argument("--baselight", type=str, help="Path to baselight file.")
parser.add_argument("--xytech", type=str, help="Path to xytech file.")
parser.add_argument("--process", type=str, help="Path to video file.")
args = parser.parse_args()

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["project4"]

folderlocation = ["Location"]
xytechdata = []
csvlist = [["Path", "Frames"]]
baselightdata = []

def probetimecode(video):
    probe = ffmpeg.probe(video)
    return probe.get('timecode')

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
    timecode = timecode.split(":")
    hours = timecode[0]
    minutes = timecode[1]
    seconds = timecode[2]
    frames = timecode [3]
    
    minutes += hours * 60
    seconds += minutes * 60
    frames += seconds * 24

    return frames

def addhandles(framerange):
    framerange.split("-")
    startrange = int(framerange[0])
    endrange = int(framerange[1])

    if startrange < 48:
        startrange = 0
    else:
        startrange = startrange - 48

    endrange += 48

    return f"{startrange}-{endrange}"

#project 1
if args.xytech:
    with open(args.xytech, "r") as xytech:
        data = xytech.read()
        lines = data.splitlines()
        
        if "Workorder" in lines[0]:
            workorder = lines[0].split(" ")[2]

        for line in lines:
            if "/" in line:
                folderlocation.append(line)
                folder = {
                    "Workorder": workorder,
                    "Location": line
                }
                xytechdata.append(folder)

    #xytech database
    mycol = mydb["xytech"]
    x = mycol.insert_many(xytechdata)
    print(f"Inserted xytech file info into collection {mycol.name}")

currentpath = ""
baselightpath = ""
frames = []

if args.baselight:
    with open(args.baselight, "r") as baselight:
        data = baselight.read()
        lines = data.splitlines()

        for line in lines:
            currentpath = line.split(" ")
            currentpath = [item for item in currentpath if item.strip()]
            baselightpath = currentpath[0]
            querypath = currentpath[0].removeprefix("/baselightfilesystem1/")
            for folder in folderlocation:
                if querypath in folder:
                    xytechmatch = folder
                    break

            #frames
            individualFrames = 0 #counter for amount of individual frames in a line
            frameRange = 0 #counter for amount of frame ranges in a line
            startRange = 0
            endRange = 0
            for frame in currentpath[1:]:
                if startRange == 0 and endRange == 0:
                    startRange = frame
                    endRange = frame
                    continue
                if int(frame) == int(endRange) + 1:
                    endRange = frame
                    continue
                if startRange == endRange:
                    csvlist.append([xytechmatch, startRange])
                    record = {
                        "Path": baselightpath,
                        "Frames": startRange
                    }
                    baselightdata.append(record)
                    individualFrames += 1
                    startRange = frame
                    endRange = frame
                    continue

                csvlist.append([xytechmatch, f"{startRange}-{endRange}"])
                record = {
                    "Path": baselightpath,
                    "Frames": f"{startRange}-{endRange}"
                }
                baselightdata.append(record)
                frameRange += 1
                startRange = frame
                endRange = frame

            #check if there is a remaining range to print after the loop
            if startRange != 0 and endRange != 0:
                if startRange == endRange:
                    csvlist.append([xytechmatch, startRange])
                    record = {
                        "Path": baselightpath,
                        "Frames": startRange
                    }
                    baselightdata.append(record)
                    individualFrames += 1
                else:
                    csvlist.append([xytechmatch, f"{startRange}-{endRange}"])
                    record = {
                    "Path": baselightpath,
                    "Frames": f"{startRange}-{endRange}"
                    }
                    baselightdata.append(record)
                    frameRange += 1

            print(f"{xytechmatch} Individual: {individualFrames} Ranges: {frameRange}")

    with open("project1output.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(csvlist)

    #baselight database
    mycol = mydb["baselight"]
    x = mycol.insert_many(baselightdata)
    print(f"Inserted {len(x.inserted_ids)} records from {args.baselight} into MongoDB collection {mycol.name}.")

if args.process:
    timecode = probetimecode(args.process)
    frames = toframes(timecode)