#!/usr/bin/env python3

import json
import os
import time
import urllib.parse
import urllib.request

import click
import requests
from fake_useragent import UserAgent
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException

from utils import print_log, raise_exception, ensure_file_existence, format_arg_date, dump_cookies, \
    get_uid_from_event, get_old_metadata, get_audio_ids, format_cookies_for_request


def create_driver(user_agent, show=False, system='linux', driver_location=None):
    print_log("Setting up the driver.")
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("user-agent=" + str(user_agent))

    caps = DesiredCapabilities.CHROME
    caps['loggingPrefs'] = {'performance': 'ALL'}
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}
    if system == 'mac':
        driver_location = driver_location if driver_location else '/usr/local/bin/chromedriver'
        driver = webdriver.Chrome(driver_location, desired_capabilities=caps, options=chrome_options)
    else:
        Display(visible=show, size=(1200, 600)).start()
        chrome_options.add_experimental_option("detach", True)
        driver_location = driver_location if driver_location else '/usr/bin/chromedriver'
        driver = webdriver.Chrome(driver_location, desired_capabilities=caps, options=chrome_options)
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


def enter_username_and_password(driver, username, password, slow=False, submit=True, remember_me=False):
    print_log('Entering username and password.')
    driver.get("https://alexa.amazon.com")
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

    if remember_me:
        driver.find_element_by_xpath("//div[@data-a-input-name='rememberMe']/label/i").click()
    if submit:
        driver.find_element_by_id("signInSubmit").click()
    driver.implicitly_wait(2)


def search_for_recordings(driver, start_date, system='linux'):
    print_log('Searching for recordings.')
    driver.get("https://www.amazon.com/hz/mycd/myx#/home/alexaPrivacy/activityHistory")
    driver.implicitly_wait(5)
    display_button = driver.find_element_by_id('filters-selected-bar')
    display_button.click()
    driver.implicitly_wait(1)
    filter_date_button = driver.find_element_by_class_name('filter-by-date-menu')
    filter_date_button.click()
    driver.implicitly_wait(1)
    custom_button = driver.find_element_by_id('custom-date-range-filter')
    custom_button.click()
    driver.implicitly_wait(1)

    starting_date = driver.find_element_by_id('date-start')
    if system == 'mac':
        starting_date.send_keys(Keys.COMMAND + 'A')
    else:
        starting_date.clear()
    starting_date.send_keys(start_date)


def check_for_uid(d):
    return (d.get('method') == 'Network.responseReceived') \
           and ('params' in d) \
           and ('response' in d.get('params')) \
           and ('url' in d.get('params').get('response')) \
           and ('uidArray[]=' in d.get('params').get('response').get('url'))


def get_audio_data_from_event_old(e, username, password):
    url = e.get('params').get('response').get('url')
    request = urllib.request.Request(url)
    base64string = bytes('%s:%s' % (username, password), 'ascii')
    request.add_header("Authorization", "Basic %s" % base64string)
    result = urllib.request.urlopen(request)
    return result.read()


def reveal_all_recordings(driver):
    hidden_recordings = True
    while hidden_recordings:
        hidden_recordings = False
        show_more_buttons = driver.find_elements_by_xpath("//div[@class='full-width-message clickable']")

        for button in show_more_buttons:
            if button.text == 'Show more':
                hidden_recordings = True
                button.click()


def find_div_id_in_metadata(id_to_find, old_metadata):
    for metadata_info in old_metadata:
        for key, val in metadata_info.items():
            if key == 'div_id' and val == id_to_find:
                return metadata_info
    return None


def extract_recording_metadata(recording_boxes, driver, old_metadata, download_duplicates):
    print_log('Extracting the metadata from each recording: ')
    recording_metadata = list()
    indices_to_download = list()

    for i, recording_box in enumerate(recording_boxes):
        box_div_id = recording_box.get_property('id')

        # Skip this recording if it is already documented.
        if download_duplicates is False:
            old_metadata_info = find_div_id_in_metadata(box_div_id, old_metadata)
            if old_metadata_info is not None:
                recording_metadata.append(old_metadata_info)
                print_log(f"Skipping recording #{i + 1}.")
                continue

        indices_to_download.append(i)

        print_log(f'Working on recording #{i + 1}.')
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
            'device': recording_device,
            'div_id': box_div_id,
        }
        recording_metadata.append(metadata)

        # Open box for audio ID extraction later
        expand_button_list = recording_box.find_elements_by_xpath(".//button")
        if len(expand_button_list) == 0:
            print_log("ERROR: The script cannot find the button to expand the recording box. This means that "
                      "this recording cannot be extracted (but the metadata can still be).")
            indices_to_download.append(i)
        else:
            expand_button_list[0].click()
            time.sleep(1)

    return recording_metadata, indices_to_download


def extract_uid_from_recordings(driver, indices_to_download, metadata):
    print_log('Extracting Audio ID.')
    events = [json.loads(entry['message'])['message'] for entry in driver.get_log('performance')]
    response_events = list(filter(check_for_uid, events))

    if len(response_events) != len(indices_to_download):
        print_log('WARNING: The number of network events to find the uid do not equal the number of recordings'
                  'there are on the alexa website. This could be because the site format has changed. The '
                  'audio ID will not be noted down in this run.')
    else:
        for idx, event in enumerate(response_events):
            idx_to_update = indices_to_download[idx]
            metadata[idx_to_update].update({'audio_id': get_uid_from_event(event)})


def get_wav_from_audio_id(audio_id, user_agent, cookies, audio_file):
    url_base = 'https://www.amazon.com/alexa-privacy/apd/rvh/audio?uid='
    full_url = url_base + audio_id
    headers = {'User-Agent': user_agent}
    response = requests.get(full_url, headers=headers, cookies=cookies)
    with open(audio_file, "wb+") as f:
        f.write(response.content)


def download_wav_files(audio_ids, user_agent, cookies, output_file):
    print_log('Downloading wav files.')
    for i, audio_id in enumerate(audio_ids):
        audio_file = os.path.join(output_file, f'{i}.wav')
        get_wav_from_audio_id(audio_id, user_agent, cookies, audio_file)


def setup(driver, start_date, cookies_file, config_file, info_file, output_file, download_duplicates, user_agent, system):
    print_log('Starting metadata extraction.')
    with open(config_file, "r") as f:
        credentials = json.load(f)
    username = credentials['username']
    password = credentials['password']

    enter_username_and_password(driver, username, password, slow=True, remember_me=True)
    captcha(driver, username, password)
    email_verification(driver)

    print_log("Loading old cookies.")

    cookies = driver.get_cookies()
    dump_cookies(cookies_file, cookies)

    try:
        search_for_recordings(driver, start_date, system=system)
        reveal_all_recordings(driver)
    except WebDriverException:
        search_for_recordings(driver, start_date, system=system)

    recording_boxes = driver.find_elements_by_class_name('apd-content-box')
    old_recording_metadata = get_old_metadata(info_file)

    recording_metadata, indices_to_download = \
        extract_recording_metadata(recording_boxes, driver, old_recording_metadata, download_duplicates)

    extract_uid_from_recordings(driver, sorted(indices_to_download), recording_metadata)

    with open(info_file, "w+") as f:
        json.dump(recording_metadata, f, indent=4)

    recording_ids = get_audio_ids(recording_metadata)
    formatted_cookies = format_cookies_for_request(cookies)
    download_wav_files(recording_ids, user_agent, formatted_cookies, output_file)

    driver.quit()


def get_recordings(config_file, info_file, cookies_file, output_dir, end_date, system, show, download_duplicates,
                   driver_location):
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

    driver = create_driver(user_agent, show=show, system=system, driver_location=driver_location)
    setup(driver, end_date, cookies_file, config_file, info_file, output_dir, download_duplicates, user_agent, system)


@click.command()
@click.option("-c", "--config", type=str, help="specify a file for credential information", required=False,
              default="credentials.json")
@click.option("-i", "--info", type=str, help="specify a file for the recording info", required=False,
              default="recordinginfo.json")
@click.option("-C", "--cookies", type=str, help="specify a file for the stored cookies", required=False,
              default="cookies.json")
@click.option("-o", "--output", type=str, help="specify a directory to output files", required=False,
              default="output")
@click.option("-d", "--date", type=str, help="specify a date in the format 'YYYY/MM/DD HH:MM:SS'",
              required=True)
@click.option("--system", type=click.Choice(['linux', 'mac'], case_sensitive=False), required=False, default='linux',
              help='Specify the OS you are working on (linux or mac)')
@click.option('--show', is_flag=True, help="show the chrome window as it searches for recordings.")
@click.option('--download-duplicates', is_flag=True, help="download recordings that have already been downloaded.")
@click.option('--driver', type=str, help="Specify file location of driver.")
def main(config, info, cookies, output, date, system, show, download_duplicates, driver):
    show = False if show is None else show
    download_duplicates = False if download_duplicates is None else download_duplicates
    ensure_file_existence(config)
    get_recordings(config, info, cookies, output, format_arg_date(date), system, show, download_duplicates, driver)


if __name__ == "__main__":
    main()
