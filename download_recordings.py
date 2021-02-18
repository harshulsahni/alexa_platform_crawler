#!/usr/bin/env python3

import argparse
import json
import os
import time
import urllib.request

import requests
from fake_useragent import UserAgent
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils import print_log, raise_exception, ensure_file_existence, format_arg_date


def create_driver(user_agent, show=False, system='linux'):
    print_log("Setting up the driver.")
    chrome_options = webdriver.ChromeOptions()
    if not show:
        Display(visible=False, size=(1200, 600)).start()
    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_argument("user-agent=" + str(user_agent))

    caps = DesiredCapabilities.CHROME
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}
    if system == 'mac':
        driver = webdriver.Chrome('/usr/local/bin/chromedriver', desired_capabilities=caps, options=chrome_options)
    else:
        driver = webdriver.Chrome(executable_path="/usr/bin/chromedriver", desired_capabilities=caps, options=chrome_options)
    print_log("Finished setting up the driver.")
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
        print_log("No 2 Step Verification Required!")


def captcha(driver, username, password):
    try:
        image = driver.find_element_by_id("auth-captcha-image")
    except NoSuchElementException:
        print_log("No Captcha!")
        return

    print_log("Captcha detected.")
    src = image.get_attribute('src')

    with open("captcha.jpg", "wb") as f:
        f.write(requests.get(src).content)
        f.close()

    enter_username_and_password(driver, username, password, slow=True, submit=False)

    verification = driver.find_element_by_id("auth-captcha-guess")
    user_guess = print_log("Enter your captcha guess: ", input_flag=True)
    verification.send_keys(user_guess)

    submit = driver.find_element_by_id("signInSubmit")

    with open("test.html", "w") as f:
        f.write(driver.page_source)

    submit.click()
    print_log('Submitting captcha.')
    driver.implicitly_wait(5)


def email_verification(driver):
    url = driver.current_url
    email_verification_element = driver.find_elements_by_id('resend-transaction-approval')
    if len(email_verification_element) == 0:
        print_log('No email verification!')
        return
    print_log('ACTION NEEDED: Waiting for email verification. Please check your email.')
    while driver.current_url == url:
        time.sleep(2)
    print_log('Email approved.')
    return


def enter_username_and_password(driver, username, password, slow=False, submit=True):
    print_log('Entering username and password.')
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
    driver.implicitly_wait(2)


def search_for_recordings(driver, start_date):
    print_log('Searching for recordings.')
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


def check_for_uid(d):
    return (d.get('method') == 'Network.responseReceived') \
           and ('params' in d) \
           and ('response' in d.get('params')) \
           and ('url' in d.get('params').get('response')) \
           and ('uidArray[]=' in d.get('params').get('response').get('url'))


def get_audio_data_from_event(e, username, password):
    url = e.get('params').get('response').get('url')
    request = urllib.request.Request(url)
    base64string = bytes('%s:%s' % (username, password), 'ascii')
    request.add_header("Authorization", "Basic %s" % base64string)
    result = urllib.request.urlopen(request)
    return result.read()


def open_all_recordings(driver):
    hidden_recordings = True
    while hidden_recordings:
        hidden_recordings = False
        show_more_buttons = driver.find_elements_by_xpath("//div[@class='full-width-message clickable']")

        for button in show_more_buttons:
            if button.text == 'Show more':
                hidden_recordings = True
                button.click()


def extract_recording_metadata(recording_boxes, driver):
    print_log('Extracting the metadata from each recording: ')
    recording_metadata = list()

    for i, recording_box in enumerate(recording_boxes):
        print_log(f'Working on recording #{i+1}.')
        recording_date = str()
        recording_time = str()
        recording_device = str()

        message_div = \
            recording_box.find_elements_by_xpath(".//div[@class='record-summary-preview customer-transcript']")

        if len(message_div) == 0:
            audio_not_understood_msg = \
                recording_box.find_elements_by_xpath(".//div[@class='record-summary-preview replacement-text']")

            if len(audio_not_understood_msg) == 0:
                print_log("ERROR: Cannot seem to find the transcription of the recording. Going to error out.")
                raise_exception(NoSuchElementException('Could not find the transcription of the recording.'),
                                driver)
            else:
                message_div = audio_not_understood_msg

        recording_text = message_div[0].text

        date_time_info = recording_box.find_elements_by_xpath(".//div[@class='item']")
        if len(date_time_info) < 3:
            print_log("ERROR: The recording div does not seem to have ALL of the following info: "
                      "Date, Time, and device. Going to error out.")
            raise_exception(NoSuchElementException("The recording div does not have all the necessary "
                                                   "metadata for extraction, or the page layout has changed."),
                            driver)
        else:
            recording_date = date_time_info[0].text
            recording_time = date_time_info[1].text
            recording_device = date_time_info[2].text

        metadata = {
            'message': recording_text,
            'date': recording_date,
            'time': recording_time,
            'device': recording_device
        }
        recording_metadata.append(metadata)

    return recording_metadata


def setup(driver, start_date, cookies_file, config_file, info_file):
    print_log('Starting metadata extraction.')
    driver.get("https://alexa.amazon.com")
    with open(config_file, "r") as f:
        credentials = json.load(f)
    username = credentials['username']
    password = credentials['password']

    enter_username_and_password(driver, username, password, slow=True)
    captcha(driver, username, password)
    email_verification(driver)

    print_log('Dumping cookies.')
    cookies = driver.get_cookies()
    with open(cookies_file, "w") as f:
        json.dump(cookies, f, indent=4)

    search_for_recordings(driver, start_date)
    open_all_recordings(driver)
    recording_boxes = driver.find_elements_by_class_name('apd-content-box')
    recording_metadata = extract_recording_metadata(recording_boxes, driver)

    # # mainBox is the div for the commands
    # recordings = []
    # navigation_available = True
    #
    # while navigation_available:
    #     ipdb.set_trace()
    #     try:
    #         events = [json.loads(entry['message'])['message'] for entry in driver.get_log('performance')]
    #         response_events = list(filter(check_for_uid, events))
    #         for e in response_events:
    #             audio_data = get_audio_data_from_event(e, username, password)
    #             audio_id = audio_data.get('utteranceId')
    #             is_audio_playable = audio_data.get('audioPlayable')
    #             date = 1
    #
    #         elem = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located(
    #         (By.CLASS_NAME, "apd-content-box")))
    #
    #         for e in elem:
    #             text_info = e.find_element_by_class_name("textInfo")
    #             audio_id = text_info.find_element_by_class_name("playButton").get_attribute("attr")
    #             try:
    #                 text_elem = text_info.find_element_by_class_name("summaryCss")
    #             except NoSuchElementException:
    #                 text_elem = text_info.find_element_by_class_name("summaryNotAvailableCss")
    #
    #             text = text_elem.text
    #             date_elem = text_info.find_element_by_class_name("subInfo")
    #             date = date_elem.text
    #             recording_info = {
    #                 "audio-id": audio_id,
    #                 "text": text,
    #                 "date": date
    #             }
    #             recordings.append(recording_info)
    #
    #         next_elem = WebDriverWait(driver, 10).until(
    #             EC.element_to_be_clickable((By.CLASS_NAME, "paginationControls"))).find_element_by_id("nextButton")
    #
    #         navigation_available = "navigationAvailable" in next_elem.get_attribute("class")
    #         if navigation_available:
    #             next_elem.click()
    #     except TimeoutException as e:
    #         print(e)

    with open(info_file, "w") as f:
        json.dump(recording_metadata, f, indent=4)

    driver.quit()


def get_recordings(config_file, info_file, cookies_file, output_dir, end_date, show):
    url = "https://www.amazon.com/hz/mycd/playOption?id="

    ua = UserAgent()
    user_agent = ua.random
    
    last_credential_path = "./last_credentials.json"
    # raise err if someone change use new account
    if os.path.isfile(last_credential_path):
        with open(last_credential_path, "r") as old_c:
            old_credential = json.load(old_c)
        with open(config_file, "r") as new_c:
            new_credential = json.load(new_c)

        if old_credential != new_credential:
            os.remove(last_credential_path)
            raise ValueError("You have changed credential settings, "
                             "please save and delete the recordinginfo.json file.")
    else:
        # need to make a last_credential file if there is no such a file
        with open(last_credential_path, "w") as old_c:
            with open(config_file, "r") as new_c:
                new_cred = json.load(new_c)
                json.dump(new_cred, old_c)

    with open(cookies_file, "r") as f:
        cookies = json.load(f)

    driver = create_driver(user_agent, show=show)
    setup(driver, end_date, cookies_file, config_file, info_file)

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # with open(info_file, "r") as f:
    #     recordings = json.load(f)

    formatted_cookies = {}
    for cookie in cookies:
        formatted_cookies.update({cookie["name"]: cookie["value"]})

    # for recording in recordings:
    #     audio_id = recording["audio-id"]
    #
    #     recording_date = recording["date"]
    #     headers = {
    #         'User-Agent': user_agent
    #     }
    #
    #     formatted_date = format_date(recording_date)
    #     print('downloading')
    #     audio_file = get_file_path(formatted_date, output_dir, "wav")
    #     text_file = get_file_path(formatted_date, output_dir, "txt")
    #
    #     response = requests.get(url + audio_id, headers=headers, cookies=formatted_cookies)
    #
    #     text = recording["text"]
    #     with open(audio_file, "wb") as f:
    #         f.write(response.content)
    #
    #     with open(text_file, "w") as f:
    #         f.write(text)


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
    parser.add_argument("-s", "--show", type=bool, help="show the chrome window as it searches for recordings. ",
                        default=False, required=False)

    args = parser.parse_args()
    ensure_file_existence(args.config)
    get_recordings(args.config, args.info, args.cookies, args.output, format_arg_date(args.date), args.show)


if __name__ == "__main__":
    main()
