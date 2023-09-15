import sys
import os
import time
import json
import glob
import pathlib
import requests
import subprocess
from libretranslatepy import LibreTranslateAPI
from flask import Flask, request
import xml.etree.ElementTree as ET


import re
from config import *
from time import sleep
from progress.bar import Bar

def converttobool(in_bool):
    value = str(in_bool).lower()
    if value in ('false', 'off', '0'):
        return False
    else:
        return True

lt = LibreTranslateAPI(libretranslate)

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def receive_webhook():
    if request.headers.get("source") == "Tautulli":
        payload = request.json
    else:
        payload = json.loads(request.form['payload'])
    event = payload.get("event")
    if ((event == "library.new" or event == "added") and procaddedmedia) or ((event == "media.play" or event == "played") and procmediaonplay):
        print("[*] Webhook received!")
        fullpath = payload.get("file")

        
        filename = pathlib.Path(fullpath).name
        filepath = os.path.dirname(fullpath)
        filenamenoextension = filename.replace(pathlib.Path(fullpath).suffix, "")
        filepathnoextension = filepath + "\\" + filenamenoextension

        if skipifinternalsublang in str(subprocess.check_output("ffprobe -loglevel error -select_streams s -show_entries stream=index:stream_tags=language -of csv=p=0 \"{}\"".format(fullpath), shell=True)):
            print("[*] File already has an internal sub we want, skipping generation")
            return 
        elif len(glob.glob("{}/{}*auto*".format(filepath, filenamenoextension))) > 0:
            print("We already have a subgen created for this file, skipping it")
            return "We already have a subgen created for this file, skipping it"
           

        
        if os.path.isfile("{}.subgen.srt".format(filepathnoextension)):
            print("[*] This media processed in the past. BUT translation not done yet.")
            run_translate(fullpath, filepathnoextension)

            return ""
        elif os.path.isfile("{}.{}.ar-auto.srt".format(filepathnoextension, whisper_model)):
            print("[*] Media fully processed.")
            return  ""
        else:
            # strip_audio(fullpath, filepathnoextension)
            run_whisper(fullpath, filepathnoextension)

        time.sleep(2)
        run_translate(fullpath, filepathnoextension)

    else:
        print("[*] Weird Webhook: [{}], ignoring . . .".format(event))
        return ""
    return ""


# def strip_audio(fullpath, outfilename):
#     print("Starting strip audio")
#     command = "ffmpeg -y -i \"{}\" -ar 16000 -ac 1 -c:a pcm_s16le \"{}.audio.wav\"".format(
#         fullpath, outfilename)
#     # print("Command: " + command)
#     subprocess.call(command, shell=True)
#     print("Done stripping audio")

def run_whisper(fullpath, filepathnoextension):
    print("[*} Starting whisper")

    command = ("{} {} -l {} -m \"{}\" -p {} -t {} -f \"{}\" -osrt".format(mainexe,(("-gpu" + ' "' + device_name + '"') if (isgpu) else " "), 
                namesublang, whisper_model_path, whisper_processors, whisper_threads, fullpath))

    if (whisper_speedup):
        command = command.replace("-osrt", "-osrt -su")
    print("Command: " + command)
    subprocess.call(command, shell=True)

    os.rename(filepathnoextension + ".srt", filepathnoextension + ".subgen.srt")
    print("Done with whisper")

def run_translate(fullpath, filepathnoextension):
    print("Starting translation")
    buff = ""
    count = 0 
    try:
        extract = open("{}.subgen.srt".format(filepathnoextension), 'r')
    except Exception as e:
        print("[-] [{}] Could not be opened!".format(fullpath))
        return
    totalLines = len(extract.readlines())
    extract.seek(0)
    with Bar('Processing',max = totalLines) as bar:
        for line in extract:
            lineTranslate = ""
            count += 1
            if(line == "ï»¿1\n"):
                buff = buff + "1\n"
                continue
            joinedLine = " ".join(re.findall("[a-zA-Z]+", line))
            if(joinedLine != ""):
                try:
                    lineTranslate = lt.translate("{}".format(joinedLine.lower()), namesublang,"{}".format(targetlang))

                    if(line[0] == '['):
                        buff = buff + '[' + lineTranslate + ']\n'
                    elif(line[0] == ')'):
                        buff = buff + '(' + lineTranslate + ')\n'
                    elif(line[0] == '"'):
                        buff = buff + '"' + lineTranslate + '"\n'
                    elif(lineTranslate == ""):
                        buff = buff + line
                    else:
                        buff = buff + lineTranslate + "\n"
                except Exception as e:
                    print("[-] [{}] Failed to translate, keeping it".format(line))
                    buff = buff + line      #attach original line
                    continue
            else:
                buff = buff + line
            bar.next()
    extract.close()

    ogfinalsubname = "{0}.{1}.{2}-auto".format(filepathnoextension, whisper_model, namesublang)
    os.rename("{}.subgen.srt".format(filepathnoextension), "{}.srt".format(ogfinalsubname))

    if whisper_speedup:
        print("[*] This is a speedup run!")
        print(whisper_speedup)
        finalsubname = "{0}.{1}.speedup.{2}-auto".format(filepathnoextension, whisper_model, targetlang)
    else:
        print("[*] No speedup")
        finalsubname = "{0}.{1}.{2}-auto".format(filepathnoextension, whisper_model, targetlang)

    if(targetlang == "ar"):
        with open("{}.srt".format(finalsubname), 'w', encoding='utf-8') as output_file:
            output_file.write(buff)
    else:
        with open("{}.srt".format(finalsubname), 'w') as output_file:
            output_file.write(buff)
    output_file.close()
    print("[*] Done with translation")

print("Starting webhook!")
if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=int(webhookport))