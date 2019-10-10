wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb

wget https://chromedriver.storage.googleapis.com/2.37/chromedriver_linux64.zip
unzip chromedriver_linux64.zip

sudo cp chromedriver /usr/bin/chromedriver
sudo chown root /usr/bin/chromedriver
sudo chmod 755 /usr/bin/chromedriver
