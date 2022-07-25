# Download Subtitles

Download subtitles from opensubtitles.org by right click on the video file.

example:

![](images/download_subs_usage.gif)

A little python script to download subtitles from opensubtitles.org.

# Usage:

Right click on any video file or files, send to download_subs.cmd.

# Requirements:

-Windows. (just for the send to part)

-Python 3.

# Setup:

Download the downloads_subs.py file.

On windows "Ctrl+R" and run "shell:sendto"
this will open the "send to" directory so we can add our bash script.

To run the python script you must create download_subs.cmd (this name will show on the send to menu)

download_subs.cmd script that sends the path of the selected file or files to our python script

```
@echo off
cls
python3 path_to_script\download_subs.py %*
pause
```
