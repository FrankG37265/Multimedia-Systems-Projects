import argparse
import ffmpeg
import sys
import os

parser = argparse.ArgumentParser(description="A script that uses ffmpeg to generate thumbnails, gifs, and watermarks.")
parser.add_argument("folder", type=str, help="The input folder.")
parser.add_argument("--filename", type=str, help="Specific file to use if only one file is needed.")
parser.add_argument("--name", type=str, help="The name to use in the versioning.")
parser.add_argument("--confidential", action='store_true', help="Whether to add a confidential watermark.")
parser.add_argument("--GC", action='store_true', help="Create a gif from latest pngs in the folder.")
parser.add_argument("--ME", action='store_true', help="Grab metadata from the input file.")
parser.add_argument("--TC", action='store_true', help="Generate a thumbnail from the input file.")
parser.add_argument("--WM", action='store_true', help="Add a watermark to the input file.")

args = parser.parse_args()

# NONAME is just since it's only needed for the first version
def version_update(input_file, name="NONAME"):
    if name not in input_file:
        new_file = input_file.replace('.png', f'_VFX_{name}_v01.png')
        return new_file
    version = int(input_file.split('v0')[1].split('.')[0]) + 1
    new_file = input_file.replace(f'v0{version-1:01d}', f'v0{version:01d}')
    return new_file

def find_latest_version(folder, input):
    files = os.listdir(folder)
    versions = [f for f in files if input in f and ".txt" not in f]
    latest = (f"{folder}{max(versions)}")
    return latest

def grab_metadata(input_file):
    output_file = input_file.rsplit('.', 1)[0] + '_metadata.txt'
    probe = ffmpeg.probe(input_file)

    formatinfo = probe.get('format', {})
    streams = probe.get('streams', [])
    with open(output_file, 'w') as f:
        f.write(f"Format: {formatinfo.get('format_long_name')}\n")
        f.write(f"Duration: {formatinfo.get('duration')} seconds\n")
        f.write(f"Size: {formatinfo.get('size')} bytes\n")
        f.write(f"Bitrate: {formatinfo.get('bit_rate')} bits/s\n\n")

        for stream in streams:
            f.write(f"Stream #{stream.get('index')}:\n")
            f.write(f"Codec: {stream.get('codec__name')}\n")
            f.write(f"Codec Type: {stream.get('codec_type')}\n")
            f.write(f"Width: {stream.get('width', 'N/A')}\n")
            f.write(f"Height: {stream.get('height', 'N/A')}\n")
            f.write(f"Frame Rate: {stream.get('r_frame_rate', 'N/A')}\n")
            f.write(f"Bitrate: {stream.get('bit_rate', 'N/A')} bits/s\n\n")

def watermark(input_file, confidential=False, name="NONAME"):
    output_path = version_update(input_file, name)
    output_file = output_path.split("/")[1] # Remove folder from output file name for watermark text
    if confidential:
        (
            ffmpeg
            .input(input_file)
            .drawtext(text="CONFIDENTIAL", fontcolor='white', fontsize='w/8', x="(w-text_w)/2", y="(h-text_h)/2")
            .output(output_path, update=1)
            .run()
        )    
    else:
        (
            ffmpeg
            .input(input_file)
            .drawtext(text=output_file, fontcolor='white', fontsize=24, x="w-text_w-10", y="10")
            .output(output_path, update=1)
            .run()
        )

def generate_thumbnail(input_file, name="NONAME"):
    output_file = version_update(input_file, name)
    (
        ffmpeg
        .input(input_file)  # ss=1 is pull image from one second in
        .filter('scale', 320, -1)
        .output(output_file, vframes=1)
        .run()
    )
    print(f"\n\nThumbnail generated and saved as {output_file}")

def create_gif(folder, files, name):
    streams = []
    for file in files:
        stream = (
            ffmpeg
            .input(file, loop=1, t=1)
            .filter('scale', 320, 180, force_original_aspect_ratio='decrease')
            .filter('pad', 320, 180, '(ow-iw)/2', '(oh-ih)/2')
            .filter('setsar', '1')
        )
        streams.append(stream)

    (
        ffmpeg
        .concat(*streams, v=1, a=0)
        .output(f"{folder}MCU_chaja_VFX_{name}_v01.gif", r=24)
        .run()
    )

# Check for input
if not args.folder:
    print("Please provide an input folder.")
    sys.exit(1)

if not args.name:
    print("Please provide a name to use in the versioning with the --name argument.")
    sys.exit(1)

if args.WM:
    if not args.filename: # If no specific file is provided, watermark latest of all three
        watermark(find_latest_version(folder=args.folder, input="avengers"), name=args.name)
        watermark(find_latest_version(folder=args.folder, input="drdoom"), name=args.name)
        watermark(find_latest_version(folder=args.folder, input="infinity"), name=args.name)
    else:
        watermark(find_latest_version(folder=args.folder, input=args.filename), name=args.name)

if args.TC:
    if not args.filename: # If no specific file is provided, create thumbnail of latest of all three
        generate_thumbnail(find_latest_version(folder=args.folder, input="avengers"), name=args.name)
        generate_thumbnail(find_latest_version(folder=args.folder, input="drdoom"), name=args.name)
        generate_thumbnail(find_latest_version(folder=args.folder, input="infinity"), name=args.name)
    else:
        generate_thumbnail(find_latest_version(folder=args.folder, input=args.filename), name=args.name)

if args.GC:
    files = []
    files.append(find_latest_version(folder=args.folder, input="avengers"))
    files.append(find_latest_version(folder=args.folder, input="drdoom"))
    files.append(find_latest_version(folder=args.folder, input="infinity"))
    create_gif(args.folder, files, name=args.name)

if args.ME:
    if not args.filename: # If no specific file is provided, grab metadata of latest of all three
        grab_metadata(find_latest_version(folder=args.folder, input="avengers"))
        grab_metadata(find_latest_version(folder=args.folder, input="drdoom"))
        grab_metadata(find_latest_version(folder=args.folder, input="infinity"))

    elif "MCU" in args.filename: # gif metadata
        files = []
        files.append(find_latest_version(folder=args.folder, input="avengers"))
        files.append(find_latest_version(folder=args.folder, input="drdoom"))
        files.append(find_latest_version(folder=args.folder, input="infinity"))
        grab_metadata(find_latest_version(folder=args.folder, input=args.filename))
        with open(f"{find_latest_version(folder=args.folder, input=args.filename).rsplit('.', 1)[0]}_metadata.txt", 'a') as f:
            f.write(f"\n\nAll files included in gif: {files}\n")
    else:
        grab_metadata(find_latest_version(folder=args.folder, input=args.filename))

if args.confidential: # Add a confidential watermark AND THEN a regular watermark on top of that
    if not args.filename: # If no specific file, watermark all three
        watermark(find_latest_version(folder=args.folder, input="avengers"), confidential=True, name=args.name)
        watermark(find_latest_version(folder=args.folder, input="avengers"), name=args.name)
        watermark(find_latest_version(folder=args.folder, input="drdoom"), confidential=True, name=args.name)
        watermark(find_latest_version(folder=args.folder, input="drdoom"), name=args.name)
        watermark(find_latest_version(folder=args.folder, input="infinity"), confidential=True, name=args.name)
        watermark(find_latest_version(folder=args.folder, input="infinity"), name=args.name)

    else:
        watermark(find_latest_version(folder=args.folder, input=args.filename), confidential=True, name=args.name)
        watermark(find_latest_version(folder=args.folder, input=args.filename), name=args.name)

