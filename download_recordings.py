#!/usr/bin/env python3

import argparse
import datetime

import re
import sys
import json

import pytz
import requests
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait

import os
import os.path as path


def setup(start_date, cookies_file, config_file, info_file):
    # firefox_options = webdriver.FirefoxOptions()
    chrome_options = webdriver.ChromeOptions()

    # firefox_options.headless = True

    chrome_options.add_experimental_option("detach", True)
    # chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--window-size=1920,1080")
    #  chrome_options.add_argument("--start-maximized")
    # chrome_options.add_argument("window-size=1200x600")

    # driver = webdriver.Firefox(options=firefox_options)
    driver = webdriver.Chrome(options=chrome_options)
    try:
        # driver.set_window_size(1680, 1050)
        driver.get("https://alexa.amazon.com")

        username = driver.find_element_by_id("ap_email")
        password = driver.find_element_by_id("ap_password")

        with open(config_file, "r") as f:
            credentials = json.load(f)

        username.send_keys(credentials["username"])
        password.send_keys(credentials["password"])

        driver.find_element_by_id("signInSubmit").click()

        driver.get("https://www.amazon.com/hz/mycd/myx#/home/alexaPrivacy/activityHistory")

        cookies = driver.get_cookies()
        with open(cookies_file, "w") as f:
            json.dump(cookies, f, indent=4)

        time_picker = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "timePickerDesktop")))

        select = Select(time_picker)
        select.select_by_value("custom")
        calendar = driver.find_element_by_id("calendarsForCustom")
        calendar.find_element_by_xpath("//input[@id='endDateId']").send_keys(
            datetime.datetime.now(tz=pytz.timezone("America/Los_Angeles")).strftime("%m/%d/%Y"))

        calendar.find_element_by_xpath("//input[@id='startDateId']").send_keys(start_date)
        driver.find_element_by_id("submit").click()

        # mainBox is the div for the commands
        recordings = []
        navigation_available = True

        while navigation_available:
            try:

                elem = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "mainBox")))

                for e in elem:
                    text_info = e.find_element_by_class_name("textInfo")
                    audio_id = text_info.find_element_by_class_name("playButton").get_attribute("attr")
                    try:
                        text_elem = text_info.find_element_by_class_name("summaryCss")
                    except NoSuchElementException:
                        text_elem = text_info.find_element_by_class_name("summaryNotAvailableCss")

                    text = text_elem.text
                    date_elem = text_info.find_element_by_class_name("subInfo")
                    date = date_elem.text
                    recording_info = {
                        "audio-id": audio_id,
                        "text": text,
                        "date": date
                    }
                    recordings.append(recording_info)

                next_elem = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "paginationControls"))).find_element_by_id("nextButton")

                navigation_available = "navigationAvailable" in next_elem.get_attribute("class")
                if navigation_available:
                    next_elem.click()
            except TimeoutException:
                break

        with open(info_file, "w") as f:
            json.dump(recordings, f, indent=4)
    finally:
        driver.quit()


def format_date(amazon_date):
    match = re.search(
        r'(Jan(uary)?|Feb(ruary)?|Mar(ch)?|Apr(il)?|May|Jun(e)?|Jul(y)?|Aug(ust)?|Sep(tember)?|Oct(ober)?|'
        r'Nov(ember)?|Dec(ember)?)\s+\d{1,2},\s+\d{4}\s+at\s+\d{2}:\d{2}\s+[PA]M',
        amazon_date)
    date = datetime.datetime.strptime(match.group(), "%B %d, %Y at %I:%M %p")
    return date.strftime("%Y:%m:%d_%H:%M:%S")


def format_arg_date(data):
    match = re.search(r'\d{4}/\d{1,2}/\d{1,2} \d{2}:\d{2}:\d{2}', data)
    date = datetime.datetime.strptime(match.group(), "%Y/%m/%d %H:%M:%S")
    return date.strftime("%m/%d/%Y")


def get_recordings(config_file, info_file, cookies_file, output_dir, end_date):
    url = "https://www.amazon.com/hz/mycd/playOption?id="

    if not path.isfile(info_file):
        setup(end_date, cookies_file, config_file, info_file)

    if not path.exists(output_dir):
        os.mkdir(output_dir)

    with open(info_file, "r") as f:
        recordings = json.load(f)

    with open(cookies_file, "r") as f:
        cookies = json.load(f)

    formatted_cookies = {}
    for cookie in cookies:
        formatted_cookies.update({cookie["name"]: cookie["value"]})

    for recording in recordings:
        audio_id = recording["audio-id"]

        recording_date = recording["date"]
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0'
        }

        formatted_date = format_date(recording_date)

        audio_file = get_file_path(formatted_date, output_dir, "wav")
        text_file = get_file_path(formatted_date, output_dir, "txt")

        response = requests.get(url + audio_id, headers=headers, cookies=formatted_cookies)

        text = recording["text"]
        with open(audio_file, "wb") as f:
            f.write(response.content)

        with open(text_file, "w") as f:
            f.write(text)


def get_file_path(name, directory, extension):
    if not path.exists(directory + "/" + name + "." + extension):
        return directory + "/" + name + "." + extension
    else:
        i = 1
        while path.exists(str(directory + "/" + name + "_%s" + "." + extension) % i):
            i += 1
        return str(directory + "/" + name + "_%s" + "." + extension) % i


def ensure_file_existence(file_path):
    if not os.path.isfile(file_path):
        print('Error: the file {} does not exist. Please check the path'.format(file_path))
        sys.exit(-1)


def handle_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=str, help="specify a file for credential information", required=False,
                        default="credentials.json")
    parser.add_argument("-i", "--info", type=str, help="specify a file for the recording info", required=False,
                        default="recordinginfo.json")
    parser.add_argument("-C", "--cookies", type=str, help="specify a file for the stored cookies", required=False,
                        default="cookies.json")
    parser.add_argument("-o", "--output", type=str, help="specify a directory to output files", required=False,
                        default="output")
    parser.add_argument("-d", "--date", type=str, help="specify a date in the format 'YYYY:MM:DD HH:MM:SS'",
                        required=True)

    args = parser.parse_args()

    ensure_file_existence(args.config)
    return args.config, args.info, args.cookies, args.output, format_arg_date(args.date)


config, info, cookies, output, date = handle_arguments()

get_recordings(config, info, cookies, output, date)
