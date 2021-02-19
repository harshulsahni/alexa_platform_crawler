# Setup instructions:
- Clone this repository
- Enter this repo's root directory
- Run `chmod +x ./setup.sh` and `./setup.sh`
- Run `source venv/bin/activate` to use the python virtual environment. 
- Update `credentials.json` with your Alexa account email and password



Files: 

`download_recordings.py` is the script used to download all of the recordings.

Run `./download_recordings.py --help` for the help command.

A simple usage of the script is `python download_recordings.py -d "2018/08/19 11:11:11"` which gets all recordings from 08/19/2018 until the present.

**Additional Information**
* `credentials.example` is a file that shows the format for reading credentials.

* `credentials.json` is the file that actually gets read to input as the credentials

* `setup.sh` is the setup script that will set up the whole project.

* `install-chrome.sh` installs a chrome browser

* `requirements.txt` is a list of all of the dependencies needed to run `python download_recordings.py` and can be used to quickly install all of them using `pip install -r requirements.txt`.

* `recordinginfo.json` is a file that describes all of the recordings found. Delete this file when we want to forget about all of the recordings we've seen.

* `cookies.json` stores the cookies from login.
