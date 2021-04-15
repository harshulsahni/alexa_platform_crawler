# The venv module provides support for creating lightweight “virtual environments” with their own site directories,
# optionally isolated from system site directories.
sudo apt-get install python3-venv
# Change python venv interpreter 
python3 -m venv ./venv
# Install xvfb
sudo apt-get install xvfb
# Install pip
sudo apt-get install python3-pip
# Install virtualenv module for python
pip3 install virtualenv
# Install virtualenv program
sudo apt install virtualenv
# Ensure version is up to date for virtualenv
pip3 install --upgrade virtualenv
pip3 install pytz
# Enter virtual env
. venv/bin/activate
# Install dependencies 
pip install -r requirements.txt
# Exit virtual env
deactivate
# Install unzip program to extract from zip files.
sudo apt install unzip 
# Give provided install-chrome script executable permission
chmod +x install-chrome.sh
# Install chrome script.
./install-chrome.sh
# Create a credentials.json with the format of credentials.example but make sure to input your own username and password.
cp credentials.example credentials.json
# make the main download file executable
chmod +x download_recordings.py
echo "Setup has finished."
