#!/usr/bin/env python3

import argparse
import datetime
import json
import os
import os.path as path
import re
import time

import pytz
import requests
from fake_useragent import UserAgent
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


def create_driver(user_agent, show=False):
    chrome_options = webdriver.ChromeOptions()
    if not show:
        Display(visible=False, size=(1200, 600)).start()

    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_argument("user-agent=" + str(user_agent))

    driver = webdriver.Chrome(executable_path="/usr/bin/chromedriver", options=chrome_options)
    return driver


def two_step(driver):
    try:

        text_button = driver.find_element_by_xpath("//input[@type='radio' and @name='option' and @value='sms']")
        text_button.click()

        driver.find_element_by_id("continue").click()

        verification = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='text' and @name='code']")))
        # need user input
        code = input("Enter your 6 digit 2 Step Verification Code: ")

        verification.send_keys(code)

        submit = driver.find_element_by_xpath("//input[@type='submit']")
        submit.click()

    except NoSuchElementException:
        print("No 2 Step Verification Required!")


def captcha(driver, username, password):
    try:
        image = driver.find_element_by_id("auth-captcha-image")
    except NoSuchElementException:
        print("No Captcha!")
        return

    src = image.get_attribute('src')

    with open("captcha.jpg", "wb") as f:
        f.write(requests.get(src).content)
        f.close()

    enter_username_and_password(driver, username, password, slow=True, submit=False)

    verification = driver.find_element_by_id("auth-captcha-guess")
    user_guess = input("Enter your captcha guess: ")
    verification.send_keys(user_guess)

    submit = driver.find_element_by_id("signInSubmit")

    with open("test.html", "w") as f:
        f.write(driver.page_source)

    submit.click()
    driver.implicitly_wait(5)


def email_verification(driver):
    url = driver.current_url
    try:
        driver.find_element_by_id('resend-transaction-approval')
    except NoSuchElementException:
        print('No email verification!')
        return

    while driver.current_url == url:
        print('Waiting for email verification. Please check your email.')
        time.sleep(5)
    return


def enter_username_and_password(driver, username, password, slow=False, submit=True):
    username_box = driver.find_element_by_id("ap_email")
    password_box = driver.find_element_by_id("ap_password")
    username_box.clear()
    password_box.clear()

    if not slow:
        username_box.send_keys(username)
        password_box.send_keys(password)
    else:
        for key in username:
            username_box.send_keys(key)
            time.sleep(0.1)
        for key in password:
            password_box.send_keys(key)
            time.sleep(0.2)

    if submit:
        driver.find_element_by_id("signInSubmit").click()
    driver.implicitly_wait(5)


def search_for_recordings(driver, start_date, end_date):
    driver.get("https://www.amazon.com/hz/mycd/myx#/home/alexaPrivacy/activityHistory")
    driver.implicitly_wait(5)
    display_button = driver.find_element_by_id('filters-selected-bar')
    display_button.click()
    filter_date_button = driver.find_element_by_class_name('filter-by-date-menu')
    filter_date_button.click()
    custom_button = driver.find_element_by_id('custom-date-range-filter')
    custom_button.click()

    starting_date = driver.find_element_by_id('date-start')
    starting_date.clear()
    starting_date.send_keys(start_date)

    ending_date = driver.find_element_by_id('date-end')
    ending_date.clear()
    ending_date.send_keys()

    ending_date.send_keys(end_date)


def setup(driver, start_date, cookies_file, config_file, info_file):
    driver.get("https://alexa.amazon.com")
    with open(config_file, "r") as f:
        credentials = json.load(f)
    username = credentials['username']
    password = credentials['password']

    enter_username_and_password(driver, username, password, slow=True)
    captcha(driver, username, password)
    email_verification(driver)

    cookies = driver.get_cookies()
    with open(cookies_file, "w") as f:
        json.dump(cookies, f, indent=4)

    end_date = datetime.datetime.now(tz=pytz.timezone("America/Los_Angeles")).strftime("%m/%d/%Y")
    search_for_recordings(driver, start_date, end_date)
    print('done searching now tryna take recordings')
    import ipdb; ipdb.set_trace()
    try:
        print('starting elem search')
        elem = driver.find_elements_by_class_name('apd-content-box')
        print(elem)
        for e in elem:
            print(e)
    except NoSuchElementException as e:
        print(e)
        time.sleep(100)

    # mainBox is the div for the commands
    recordings = []
    navigation_available = True

    while navigation_available:
        try:
            elem = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "apd-content-box")))

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
        except TimeoutException as e:
            print(e)

    with open(info_file, "w") as f:
        json.dump(recordings, f, indent=4)


def format_date(amazon_date):
    if "Yesterday" not in amazon_date:
        match = re.search(
            r'(Jan(uary)?|Feb(ruary)?|Mar(ch)?|Apr(il)?|May|Jun(e)?|Jul(y)?|Aug(ust)?|Sep(tember)?|Oct(ober)?|'
            r'Nov(ember)?|Dec(ember)?)\s+\d{1,2},\s+\d{4}\s+at\s+\d{2}:\d{2}\s+[PA]M',
            amazon_date)
        date = datetime.datetime.strptime(match.group(), "%B %d, %Y at %I:%M %p")
    else:
        match = re.search(r'(Yesterday?)\s+at\s+\d{2}:\d{2}\s+[PA]M', amazon_date)
        yester_date = datetime.datetime.strftime(datetime.datetime.now() - datetime.timedelta(1), '%Y-%m-%d')
        replaced = match.group().replace("Yesterday", yester_date)
        date = datetime.datetime.strptime(replaced, "%Y-%m-%d at %I:%M %p")
        date.strftime("%Y:%m:%d_%H:%M:%S")
    return date.strftime("%Y:%m:%d_%H:%M:%S")


def format_arg_date(data):
    match = re.search(r'\d{4}/\d{1,2}/\d{1,2} \d{2}:\d{2}:\d{2}', data)
    date = datetime.datetime.strptime(match.group(), "%Y/%m/%d %H:%M:%S")
    return date.strftime("%m/%d/%Y")


def get_recordings(config_file, info_file, cookies_file, output_dir, end_date):
    url = "https://www.amazon.com/hz/mycd/playOption?id="

    ua = UserAgent()
    user_agent = ua.random
    
    last_credential_path = "./last_credentials.json"
    #raise err if someone change use new account
    if path.isfile(last_credential_path):
        with open(last_credential_path, "r") as old_c:
            old_credential = json.load(old_c)
        with open(config_file, "r") as new_c:
            new_credential = json.load(new_c)

        if old_credential != new_credential:
            os.remove(last_credential_path)
            raise ValueError("You have changed credential settings, please save and delete the recordinginfo.json file.")
    else:
        #need to make a last_credential file if there is no such a file
        with open(last_credential_path, "w") as old_c:
            with open(config_file, "r") as new_c:
                new_cred = json.load(new_c)
                json.dump(new_cred, old_c)

    if not path.isfile(info_file):
        driver = create_driver(user_agent, show=True)
        try:
            setup(driver, end_date, cookies_file, config_file, info_file)
        except Exception as e:
            print('ERROR DURING SETUP:')
            print(e)
            driver.quit()

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
            'User-Agent': user_agent
        }

        formatted_date = format_date(recording_date)
        print('downloading')
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
        raise OSError('Error: the file {} does not exist. Please check the path'.format(file_path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=str, help="specify a file for credential information", required=False,
                        default="credentials.json")
    parser.add_argument("-i", "--info", type=str, help="specify a file for the recording info", required=False,
                        default="recordinginfo.json")
    parser.add_argument("-C", "--cookies", type=str, help="specify a file for the stored cookies", required=False,
                        default="cookies.json")
    parser.add_argument("-o", "--output", type=str, help="specify a directory to output files", required=False,
                        default="output")
    parser.add_argument("-d", "--date", type=str, help="specify a date in the format 'YYYY/MM/DD HH:MM:SS'",
                        required=True)

    args = parser.parse_args()
    ensure_file_existence(args.config)
    get_recordings(args.config, args.info, args.cookies, args.output, format_arg_date(args.date))


if __name__ == "__main__":
    main()
