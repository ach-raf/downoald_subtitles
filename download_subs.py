#!/usr/bin/env python
import os
import sys
import time
import gzip
import struct
import hashlib
import urllib.request
from xmlrpc.client import ServerProxy

# ==== OpenSubtitles.org server settings =======================================
# XML-RPC server domain for opensubtitles.org:
osd_server = ServerProxy('https://api.opensubtitles.org/xml-rpc')
osd_username = ''
osd_password = ''
osd_language = 'en'


# Force downloading and storing UTF-8 encoded subtitles files.
opt_force_utf8 = True
# ==== Search settings =========================================================
opt_search_mode = 'hash_then_filename'


# ==== Hashing algorithm =======================================================
# Info: https://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes
# This particular implementation is coming from SubDownloader: https://subdownloader.net

def hashFile(path):
    """Produce a hash for a video file: size + 64bit chksum of the first and
    last 64k (even if they overlap because the file is smaller than 128k)"""
    try:
        longlongformat = 'Q'  # unsigned long long little endian
        bytesize = struct.calcsize(longlongformat)
        fmt = "<%d%s" % (65536 // bytesize, longlongformat)

        f = open(path, "rb")

        filesize = os.fstat(f.fileno()).st_size
        filehash = filesize

        if filesize < 65536 * 2:
            print("error", "File size error!",
                  "File size error while generating hash for this file:\n<i>" + path + "</i>")
            return "SizeError"

        buf = f.read(65536)
        longlongs = struct.unpack(fmt, buf)
        filehash += sum(longlongs)

        f.seek(-65536, os.SEEK_END)  # size is always > 131072
        buf = f.read(65536)
        longlongs = struct.unpack(fmt, buf)
        filehash += sum(longlongs)
        filehash &= 0xFFFFFFFFFFFFFFFF

        f.close()
        returnedhash = "%016x" % filehash
        return returnedhash

    except IOError:
        print("error", "I/O error!",
              "Input/Output error while generating hash for this file:\n<i>" + path + "</i>")
        return "IOError"


def auto_select_sub(video_file_name, _subtitles_result_list):
    _subtitles_selected = ''
    """Automatic subtitles selection using filename match"""
    videoFileParts = video_file_name.replace('-', '.').replace(' ', '.').replace('_', '.').lower().split('.')
    maxScore = -1

    for subtitle in _subtitles_result_list['data']:
        score = 0
        # extra point if the sub is found by hash
        if subtitle['MatchedBy'] == 'moviehash':
            score += 1
        # points for filename mach
        subFileParts = subtitle['SubFileName'].replace('-', '.').replace(' ', '.').replace('_', '.').lower().split('.')
        for subPart in subFileParts:
            for filePart in videoFileParts:
                if subPart == filePart:
                    score += 1
        if score > maxScore:
            maxScore = score
            _subtitles_selected = subtitle['SubFileName']

    return _subtitles_selected


def clean_video_title(_video_title):
    _video_title = _video_title.replace('"', '\\"')
    _video_title = _video_title.replace("'", "\\'")
    _video_title = _video_title.replace('`', '\\`')
    _video_title = _video_title.replace("&", "&amp;")
    _video_title = _video_title.replace('"', '\\"')
    _video_title = _video_title.replace("'", "\\'")
    _video_title = _video_title.replace('`', '\\`')
    _video_title = _video_title.replace("&", "&amp;")
    return _video_title


def establish_connection():
    # ==== Connection to OpenSubtitlesDownload
    try:
        return osd_server.LogIn(osd_username, hashlib.md5(osd_password[0:32].encode('utf-8')).hexdigest(),
                                osd_language, 'opensubtitles-download 4.2')
    except Exception:
        # Retry once after a delay (could just be a momentary overloaded server?)
        time.sleep(3)
        try:
            return osd_server.LogIn(osd_username, osd_password, osd_language, 'opensubtitles-download 4.2')
        except Exception:
            print('error')
            sys.exit(2)

def main(opt_languages):
    # ==============================================================================
    # ==== Main program (execution starts here) ====================================
    # ==============================================================================

    # ==== Exit code returned.
    # 0: Success, and subtitles downloaded
    # 1: Success, but no subtitles found or downloaded
    # 2: Failure

    ExitCode = 2

    # ==== File and language lists
    videoPathList = sys.argv[1:]  # get the video or videos from the args sent by the bash script
    languageList = []

    current_language = ""

    # ==== Search and download subtitles ===========================================
    session = establish_connection()
    # ==== Count languages selected for this search
    for language in opt_languages:
        languageList += list(language.split(','))

    languageCount_search = len(languageList)
    language_count_results = 0
    try:
        for current_video_path in videoPathList:
            # ==== Get file hash, size and name
            video_title = ''
            video_hash = hashFile(current_video_path)
            video_size = os.path.getsize(current_video_path)
            video_file_name = os.path.basename(current_video_path)

            # ==== Search for available subtitles
            for current_language in opt_languages:
                subtitles_search_list = []
                subtitles_result_list = {}

                if opt_search_mode in ('hash', 'hash_then_filename', 'hash_and_filename'):
                    subtitles_search_list.append(
                        {'sublanguageid': current_language, 'moviehash': video_hash, 'moviebytesize': str(video_size)})

                # Primary search
                try:
                    subtitles_result_list = osd_server.SearchSubtitles(session['token'], subtitles_search_list)
                except Exception:
                    # Retry once after a delay (we are already connected, the server may be momentary overloaded)
                    time.sleep(3)
                    try:
                        subtitles_result_list = osd_server.SearchSubtitles(session['token'], subtitles_search_list)
                    except Exception:
                        print("error", "Search error!")

                # Secondary search
                if ((opt_search_mode == 'hash_then_filename') and (
                        ('data' in subtitles_result_list) and (not subtitles_result_list['data']))):
                    subtitles_search_list[:] = []  # subtitlesSearchList.clear()
                    subtitles_search_list.append({'sublanguageid': current_language, 'query': video_file_name})
                    subtitles_result_list.clear()
                    try:
                        subtitles_result_list = osd_server.SearchSubtitles(session['token'], subtitles_search_list)
                    except Exception:
                        # Retry once after a delay (we are already connected, the server may be momentary overloaded)
                        time.sleep(3)
                        try:
                            subtitles_result_list = osd_server.SearchSubtitles(session['token'], subtitles_search_list)
                        except Exception:
                            print("error", "Search error!")

                # Parse the results of the XML-RPC query
                if ('data' in subtitles_result_list) and (subtitles_result_list['data']):

                    # Mark search as successful
                    language_count_results += 1
                    subtitles_selected = ''

                    # If there is only one subtitles (matched by file hash), auto-select it (except in CLI mode)
                    if (len(subtitles_result_list['data']) == 1) and (
                            subtitles_result_list['data'][0]['MatchedBy'] == 'moviehash'):
                        subtitles_selected = subtitles_result_list['data'][0]['SubFileName']

                    # Get video title
                    video_title = subtitles_result_list['data'][0]['MovieName']

                    # Title and filename
                    video_title = clean_video_title(video_title)

                    if not subtitles_selected:
                        subtitles_selected = auto_select_sub(video_file_name, subtitles_result_list)

                    # At this point a subtitles should be selected
                    if subtitles_selected:
                        sub_index = 0
                        sub_index_temp = 0

                        # Find it on the list
                        for item in subtitles_result_list['data']:
                            if item['SubFileName'] == subtitles_selected:
                                sub_index = sub_index_temp
                                break
                            else:
                                sub_index_temp += 1

                        # Prepare download
                        sub_url = subtitles_result_list['data'][sub_index]['SubDownloadLink']
                        sub_encoding = subtitles_result_list['data'][sub_index]['SubEncoding']
                        sub_lang_name = subtitles_result_list['data'][sub_index]['LanguageName']

                        # Use the path of the input video
                        sub_path = current_video_path.rsplit('.', 1)[
                                    0] + f".{subtitles_result_list['data'][sub_index]['SubFormat']}"

                        # Make sure we are downloading an UTF8 encoded file
                        if opt_force_utf8:
                            download_position = sub_url.find("download/")
                            if download_position > 0:
                                sub_url = sub_url[:download_position + 9] + "subencoding-utf8/" + sub_url[
                                                                                                download_position + 9:]

                        # Download and unzip the selected subtitles (with progressbar)

                        print((f">> Downloading in {subtitles_result_list['data'][sub_index]['LanguageName']} subtitles for {video_title}").replace('\\', ''))

                        tmpFile1, headers = urllib.request.urlretrieve(sub_url)
                        tmpFile2 = gzip.GzipFile(tmpFile1)
                        byteswritten = open(sub_path, 'wb').write(tmpFile2.read())
                        if byteswritten > 0:
                            process_subtitlesDownload = 0
                        else:
                            process_subtitlesDownload = 1

            # Print a message if no subtitles have been found, for any of the languages
            if language_count_results == 0:
                print('no subs available')
                ExitCode = 1
            else:
                ExitCode = 0

    except KeyboardInterrupt:
        sys.exit(1)

    # Disconnect from opensubtitles.org server, then exit
    if session and session['token']:
        osd_server.LogOut(session['token'])
    sys.exit(ExitCode)

def print_menu():  # much graphic, very handsome
    language_number = 0
    choice_conversion = []
    print(30 * '-', 'Select language for your subtitles', 30 * '-')
    for language_name in LANGUAGE_CODE:
        choice_conversion.append(language_name)
        print(f'{language_number}. {language_name}')
        language_number += 1
    
    print(f'{language_number}. Exit')
    print(66 * '-')
    return choice_conversion


def options_menu():
    choice_conversion = print_menu()
    user_choice = int(input('Subtitle language: '))
	#because the list (folder choice) in the printed menu is dynamic the showing order is the same as the index of the list
    if choice_conversion[user_choice]:
        print(f'Downloading subs in {choice_conversion[user_choice]}')
        return choice_conversion[user_choice]  
    else:
        print('Exiting...') 
        sys.exit()


# ==== Language settings =======================================================
# 1/ Change the search language by using any supported 3-letter (ISO639-2) language code:
#    > Supported language codes: https://www.opensubtitles.org/addons/export_languages.php
#    > Ex: opt_languages = ['eng','fre', 'ara']
LANGUAGE_CODE = {'English': 'eng', 'Arabic': 'ara', 'French': 'fre'}
language_choice = LANGUAGE_CODE[options_menu()]
main([language_choice])
