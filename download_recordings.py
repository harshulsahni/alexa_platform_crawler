#!alexa_env/bin/python

import json
import os
import time
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import click
import requests
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.exceptions import ProtocolError

from utils import (
    print_log,
    raise_exception,
    ensure_file_existence,
    format_date_year_month_day,
    dump_cookies,
    get_uid_from_event,
    get_old_metadata,
    get_audio_ids,
    format_cookies_for_request,
    create_user_agent,
    load_credentials,
    get_today_date_mm_dd_yyyy,
    get_full_stack,
)


def create_driver(
    user_agent: str,
    show: bool = False,
    system: str = "linux",
    driver_location: str = "/usr/local/bin/chromedriver",
) -> WebDriver:
    """
    Creates the driver based on whether the display should be shown and based on the operating
    system that the script is running on.

    :param user_agent: User agent to use for the driver. This will help during the downloading of the
        recordings.
    :param show: Whether the driver should display the window on the computer or run it wihtout a display.
        Default is False.
    :param system: The system that the script is running on. If it is not "mac", then it will default to a
        linux-based system.
    :param driver_location: Location of the driver, if the user wishes to supply one. If not, then the
        driver will use the default Chromedriver, which varies per OS.

    :return: A WebDriver with the correct settings.
    """
    print_log("Setting up the driver.")
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("user-agent=" + user_agent)

    caps = DesiredCapabilities.CHROME
    caps["loggingPrefs"] = {"performance": "ALL"}
    caps["goog:loggingPrefs"] = {"performance": "ALL"}
    if system.lower() == "mac":
        chrome_options.add_experimental_option("detach", True)
        driver_location = (
            driver_location if driver_location else "/usr/local/bin/chromedriver"
        )
        driver = webdriver.Chrome(
            driver_location, desired_capabilities=caps, options=chrome_options
        )
    else:
        Display(visible=show, size=(1200, 600)).start()
        chrome_options.add_experimental_option("detach", True)
        driver_location = (
            driver_location if driver_location else "/usr/bin/chromedriver"
        )
        driver = webdriver.Chrome(
            driver_location, desired_capabilities=caps, options=chrome_options
        )
    print_log("Finished setting up the driver.")
    return driver


def two_step(driver: WebDriver) -> None:
    """
    Performs the two-step verification, if the website asks for it. If no two step prompt is detected, then
    the script will go on to the next login step.

    :param driver: The WebDriver.

    :return: None; modifies the website given by the WebDriver.
    """
    try:
        text_button = driver.find_element_by_xpath(
            "//input[@type='radio' and @name='option' and @value='sms']"
        )
        text_button.click()

        driver.find_element_by_id("continue").click()

        verification = WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_element_located(
                (By.XPATH, "//input[@type='text' and @name='code']")
            )
        )
        # need user input
        code = input("Enter your 6 digit 2 Step Verification Code: ")

        verification.send_keys(code)

        submit = driver.find_element_by_xpath("//input[@type='submit']")
        submit.click()

    except NoSuchElementException:
        print_log("No 2 Step Verification Required!")


def captcha(driver: WebDriver, username: str, password: str) -> None:
    """
    Provides an interface for the user of the script to perform captcha verification, if the website requires it.

    :param driver: The WebDriver.
    :param username: Username for the amazon.com login.
    :param password: Password for the amazon.com login.

    :return: None; modifies the website given by the WebDriver.
    """
    try:
        image = driver.find_element_by_id("auth-captcha-image")
    except NoSuchElementException:
        print_log("No Captcha!")
        return

    print_log("Captcha detected.")
    src = image.get_attribute("src")

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
    print_log("Submitting captcha.")
    driver.implicitly_wait(5)


def email_verification(driver: WebDriver) -> None:
    """
    If amazon requests email verification, this function will halt the login process until the user has
    granted login access to the script via email.

    :param driver: The WebDriver.

    :return: None; modifies the website given by the WebDriver.
    """
    url = driver.current_url
    email_verification_element = driver.find_elements_by_id(
        "resend-transaction-approval"
    )
    if len(email_verification_element) == 0:
        print_log("No email verification!")
        return
    print_log("ACTION NEEDED: Waiting for email verification. Please check your email.")
    while driver.current_url == url:
        time.sleep(2)
    print_log("Email approved.")


def enter_username_and_password(
    driver: WebDriver,
    username: str,
    password: str,
    slow: bool = False,
    submit: bool = True,
    remember_me: bool = False,
) -> None:
    """
    Enters the username and password for amazon.com.

    :param driver: The WebDriver.
    :param username: Username for the amazon.com login.
    :param password: Password for the amazon.com login.
    :param slow: Whether the password should be entered "slowly" (with breaks of time in between) or not.
        Default is False.
    :param submit: Whether the submit button should be pressed at the end of the login or not.
        Default is True.
    :param remember_me: Whether the remember-me button should be pressed at the end of the login or not.
        Default is False.

    :return: None; modifies the website given by the WebDriver.
    """
    print_log("Entering username and password.")
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
        driver.find_element_by_xpath(
            "//div[@data-a-input-name='rememberMe']/label/i"
        ).click()
    if submit:
        driver.find_element_by_id("signInSubmit").click()
    driver.implicitly_wait(2)


def search_for_recordings(
    driver: WebDriver, start_date: str, system: str = "linux"
) -> None:
    """
    After logging in, this function traverses the recordings page to search for the required recordings.
    It enters the correct date to search by so that only relevant recordings are shown.

    :param driver: The WebDriver.
    :param start_date: The date at which the recordings want to be shown from. The date range of recordings
        goes from start_date to the date at which the script is run on.
    :param system: The operating system by which the script is running on.

    :return: None; modifies the website given by the WebDriver.
    """
    print_log("Searching for recordings.")
    driver.get("https://www.amazon.com/hz/mycd/myx#/home/alexaPrivacy/activityHistory")
    driver.implicitly_wait(10)
    display_button = driver.find_element_by_id("filters-selected-bar")
    display_button.click()
    driver.implicitly_wait(2)
    time.sleep(0.5)
    filter_date_button = driver.find_element_by_class_name("filter-by-date-menu")
    filter_date_button.click()
    driver.implicitly_wait(2)
    time.sleep(0.5)
    custom_button = driver.find_element_by_id("custom-date-range-filter")
    custom_button.click()
    driver.implicitly_wait(5)

    starting_date = driver.find_element_by_id("date-start")
    if system == "mac":
        starting_date.send_keys(Keys.COMMAND + "A")
    else:
        starting_date.clear()
    starting_date.send_keys(start_date)
    driver.implicitly_wait(5)


def check_for_uid(d: Dict[str, Any]) -> bool:
    """
    Returns whether the audio id is in the dictionary of network events or not.
    Checks:
        1. whether d["method"] is the correct network response.
        2. whether d["params"]["response"]["url"] has the text "uidArray[]=", which
            indicates that the audio ID is available in that dictionary.

    :param d: Dictionary of a single network events. Contains a lot of (extraneous) information about the
        network event.

    :return: A boolean indicating whether the audio ID is in the network event or not.
    """
    return (
        (d.get("method") == "Network.responseReceived")
        and ("params" in d)
        and ("response" in d.get("params"))
        and ("url" in d.get("params").get("response"))
        and ("uidArray[]=" in d.get("params").get("response").get("url"))
    )


def reveal_all_recordings(driver: WebDriver) -> None:
    """
    Sometimes, when a lot of recordings are requested, the page hides recordings. This function ensures that
    all recordings are shown on the page (to be downloaded and then collected).

    :param driver: The WebDriver.

    :return: None; modifies the website given by the WebDriver.
    """
    hidden_recordings = True
    while hidden_recordings:
        hidden_recordings = False
        show_more_buttons = driver.find_elements_by_xpath(
            "//div[@class='full-width-message clickable']"
        )

        # Check for more hidden recordings
        for button in show_more_buttons:
            if button.text == "Show more":
                hidden_recordings = True
                button.click()


def find_div_id_in_metadata(
    id_to_find: str, old_metadata: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Goes through the list of metadata information (located in the metadata file) and sees if any of the
    metadata objects contain the given audio ID.

    :param id_to_find: The audio ID in question.
    :param old_metadata: The metadata collected from the previous run(s) (if any).

    :return: None, if none of the metadata items contain the audio ID. Return the metadata dict if one of them
        does contain the audio ID.
    """
    for metadata_info in old_metadata:
        for key, val in metadata_info.items():
            if key == "div_id" and val == id_to_find:
                return metadata_info
    return None


def extract_recording_metadata(
    recording_boxes: List[WebElement],
    driver: WebDriver,
    old_metadata: List[Dict[str, Any]],
    download_duplicates: bool,
) -> Tuple[List[Dict[str, Any]], List[int]]:
    """
    For each recording, extracts the message text, date of message, time of message, device on which the message
    was sent, and the div_id which acts as a unique identifier for each recording.

    :param recording_boxes:
    :param driver:
    :param old_metadata:
    :param download_duplicates:

    :return: Outputs a tuple of two things:
        [0]: A list of all of the metadata for all of the recordings.
        [1]: A list of indices of which recordings need to be downloaded (and which can be skipped).
    """
    print_log("Extracting the metadata from each recording: ")
    recording_metadata = []
    indices_to_download = []
    num_recordings = len(recording_boxes)
    print_log(f"Total recordings: {num_recordings}.")

    num_skipped_recordings = 0

    for i, recording_box in enumerate(recording_boxes):
        box_div_id = recording_box.get_property("id")

        # Skip this recording if it is already documented.
        if download_duplicates is False:
            old_metadata_info = find_div_id_in_metadata(box_div_id, old_metadata)
            if old_metadata_info is not None:
                recording_metadata.append(old_metadata_info)
                print_log(f"Skipping recording #{i + 1}.")
                continue

        print_log(f"Working on recording #{i + 1}.")
        recording_date = ""
        recording_time = ""
        recording_device = ""

        message_div = recording_box.find_elements_by_xpath(
            ".//div[@class='record-summary-preview customer-transcript']"
        )

        if len(message_div) == 0:
            audio_not_understood_msg = recording_box.find_elements_by_xpath(
                ".//div[@class='record-summary-preview replacement-text']"
            )

            if len(audio_not_understood_msg) == 0:
                print_log(
                    "Cannot seem to find the transcription of the recording. Going to skip this recording."
                )
                num_skipped_recordings += 1
                continue
            else:
                message_div = audio_not_understood_msg

        recording_text = message_div[0].text

        date_time_info = recording_box.find_elements_by_xpath(".//div[@class='item']")
        if len(date_time_info) < 3:
            print_log(
                "ERROR: The recording div does not seem to have ALL of the following info: "
                "Date, Time, and device. Going to error out."
            )
            raise_exception(
                NoSuchElementException(
                    "The recording div does not have all the necessary "
                    "metadata for extraction, or the page layout has changed."
                ),
                driver,
            )
        else:
            recording_date = date_time_info[0].text
            recording_time = date_time_info[1].text
            recording_device = date_time_info[2].text

        metadata = {
            "message": recording_text,
            "date": recording_date,
            "time": recording_time,
            "device": recording_device,
            "div_id": box_div_id,
        }
        recording_metadata.append(metadata)
        indices_to_download.append(i - num_skipped_recordings)

        # Open box for audio ID extraction later
        expand_button_list = recording_box.find_elements_by_xpath(".//button")
        if len(expand_button_list) == 0:
            print_log(
                "ERROR: The script cannot find the button to expand the recording box. This means that "
                "this recording cannot be extracted (but the metadata can still be)."
            )
        else:
            expand_button_list[0].click()
            driver.implicitly_wait(1)
            time.sleep(1)

    return recording_metadata, indices_to_download


def extract_uid_from_recordings(
    driver: WebDriver, indices_to_download: List[int], metadata: List[Dict[str, Any]]
) -> None:
    """
    Adds a new "audio_id" key to the metadata for each recording, which represents the audio_id of each recording.
    This will be used to download the .wav files for each recording later on.

    :param driver: The WebDriver.
    :param indices_to_download: A list of which recordings to download (determined by their index in a list of
        recordings where the most recent recording has index 0).
    :param metadata: The metadata information for all of the recordings.

    :return: None; modifies the metadata dictionaries.
    """
    print_log("Extracting Audio ID.")
    events = [
        json.loads(entry["message"])["message"]
        for entry in driver.get_log("performance")
    ]
    response_events = list(filter(check_for_uid, events))

    if len(response_events) != len(indices_to_download):
        print_log(
            f"WARNING: The number of network events to find the uid ({len(response_events)}) "
            f"do not equal the number of recordings there are on the alexa website ({len(indices_to_download)}). "
            "This could be because the site format has changed. The audio files will not be "
            "downloaded in this run."
        )
    else:
        for idx, event in enumerate(response_events):
            idx_to_update = indices_to_download[idx]
            metadata[idx_to_update].update({"audio_id": get_uid_from_event(event)})


def get_wav_from_audio_id(
    audio_id: str, user_agent: str, cookies: Dict[str, Any], audio_file: str
) -> None:
    """
    Downloads the wav file from the audio id.

    :param audio_id: The audio id of the recording.
    :param user_agent: The user agent of the WebDriver.
    :param cookies: The cookies of the WebDriver's session.
    :param audio_file: The string location of the audio file to be saved.

    :return: None; writes the audio file to disk.
    """
    url_base = "https://www.amazon.com/alexa-privacy/apd/rvh/audio?uid="
    full_url = url_base + audio_id
    headers = {"User-Agent": user_agent}
    response = requests.get(full_url, headers=headers, cookies=cookies)
    with open(audio_file, "wb+") as f:
        f.write(response.content)


def get_recording_path(
    date: str, output_folder: str, username: str, make_new_folder: bool = True
):
    """
    Returns the path of which folder the recordings should be saved in.
    Creates the following structure:
    output_folder/
    |
    + username/
      |
      + year_month_day/
        |
        + 0/
          |
          + 0.wav
          + 1.wav

    :param date: The date at which the script ran on.
    :param output_folder: The folder name to where the recordings will be downloaded to.
    :param username: The username of the user running the script.
    :param make_new_folder: Whether the script should make a new folder (True) or return the previous folder (False).

    :return: The path of the folder where the next recordings will be saved.
    """
    year, month, day = format_date_year_month_day(date)
    cwd = os.getcwd()
    date_folder_name = f"{year}-{month}-{day}"

    output_full_path = os.path.join(cwd, output_folder)
    if not os.path.exists(output_full_path):
        print_log(
            "The output folder does not seem to be in the directory. Making a folder here: "
            f"{output_full_path}"
        )
        os.mkdir(output_full_path)

    user_folder_full_path = os.path.join(output_full_path, username)
    if not os.path.exists(user_folder_full_path):
        os.mkdir(user_folder_full_path)

    date_folder_full_path = os.path.join(user_folder_full_path, date_folder_name)
    if not os.path.exists(date_folder_full_path):
        os.mkdir(date_folder_full_path)

    recording_trials = [
        int(str(r.name)) for r in Path(date_folder_full_path).iterdir() if r.is_dir()
    ]
    new_recording_trial = max(recording_trials) + 1 if len(recording_trials) > 0 else 0
    if make_new_folder:
        next_iteration_folder = os.path.join(
            date_folder_full_path, str(new_recording_trial)
        )
        if not os.path.exists(next_iteration_folder):
            os.mkdir(next_iteration_folder)

        return next_iteration_folder
    else:
        if new_recording_trial > 0:
            next_iteration_folder = os.path.join(
                date_folder_full_path, str(new_recording_trial - 1)
            )
            return next_iteration_folder
        else:
            raise ValueError(
                "There are no recordings for this date. Therefore, the folder path of the recording "
                "cannot be returned. "
            )


def save_metadata(
    metadata: List[Dict[str, Any]], recording_path: str, metadata_file_name: str
) -> None:
    """
    Saves the metadata information at the path: {recording_path}/{metadata_file_name}

    :param metadata: Recording metadata to save.
    :param recording_path: Path where the recordings are saved.
    :param metadata_file_name: Filename of the metadata.

    :return: None.
    """
    print_log("Saving the metadata.")
    metadata_path = os.path.join(recording_path, metadata_file_name)
    with open(metadata_path, "w+") as metadata_file:
        json.dump(metadata, metadata_file, indent=4)


def save_errors(
    errors: Dict[str, Any], recording_path: str, error_file_name: str
) -> None:
    """
    Saves the error data at the path {recording_path}/{error_file_name}.

    :param errors: Error for the user.
    :param recording_path: Path where the recordings are saved.
    :param error_file_name: Filename of the error file.

    :return: None.
    """
    error_path = os.path.join(recording_path, error_file_name)
    with open(error_path, "w+") as error_file:
        json.dump(errors, error_file)


def download_wav_files(
    audio_ids: List[str],
    user_agent: str,
    cookies: Dict[str, Any],
    recording_path: str,
) -> None:
    """
    Downloads all of the wav files given audio ids and output location.

    :param audio_ids: Audio IDs of the recordings to be downloaded.
    :param user_agent: The user agent of the WebDriver.
    :param cookies: The cookies of the WebDriver's session
    :param recording_path: Directory path to save the recordings in.

    :return: None; creates a directory structure and saves all recording files appropriately.
    """

    print_log("Downloading wav files.")
    for i, audio_id in enumerate(audio_ids):
        audio_file = os.path.join(recording_path, f"{i}.wav")
        get_wav_from_audio_id(audio_id, user_agent, cookies, audio_file)


def get_recordings(
    driver: WebDriver,
    end_date: str,
    cookies_file: str,
    username: str,
    password: str,
    info_file: str,
    user_agent: str,
    path_where_recordings_are_saved: str,
    download_duplicates: bool = False,
    system: str = "linux",
) -> None:
    """
    Logs in, searches for recordings, makes recording metadata, and downloads recordings. This function is the
    heart of the program.

    :param driver: The WebDriver.
    :param end_date: The earliest date to search for recordings from. The date range of recordings will be from
        this date to the date the script is ran on.
    :param cookies_file: The file location of the previous cookies (if any).
    :param username: Username of the user.
    :param password: Password of the user.
    :param info_file: The file where the recording metadata will be saved.
    :param download_duplicates: Whether the script should find the metadata for recordings that already exist
        within the config file or not.
    :param user_agent: The user agent of the driver.
    :param path_where_recordings_are_saved: Directory path of where the recordings will be saved.
    :param system: The OS where the script is running.

    :return: None.
    """
    print_log("Starting metadata extraction.")

    enter_username_and_password(driver, username, password, slow=True, remember_me=True)
    captcha(driver, username, password)
    email_verification(driver)

    print_log("Loading old cookies.")

    cookies = driver.get_cookies()
    dump_cookies(cookies_file, cookies)

    try:
        search_for_recordings(driver, end_date, system=system)
        reveal_all_recordings(driver)
    except (
        WebDriverException,
        NoSuchElementException,
        ProtocolError,
        RemoteDisconnected,
    ):
        driver.implicitly_wait(5)
        print_log(
            "WARNING: Finding the recordings errored out. Trying to search again."
        )
        search_for_recordings(driver, end_date, system=system)
        driver.implicitly_wait(5)
        reveal_all_recordings(driver)
        driver.implicitly_wait(5)
    except ProtocolError as e:
        print_log(
            "ERROR. Amazon has closed this connection, likely because it has identified this script "
            "and will stop it. This can happen from time to time. Please run this script again."
        )
        raise e

    recording_boxes = driver.find_elements_by_class_name("apd-content-box")
    old_recording_metadata = get_old_metadata(info_file)

    recording_metadata, indices_to_download = extract_recording_metadata(
        recording_boxes, driver, old_recording_metadata, download_duplicates
    )

    extract_uid_from_recordings(driver, sorted(indices_to_download), recording_metadata)

    metadata_file_name = info_file.split("/")[-1]
    save_metadata(
        metadata=recording_metadata,
        recording_path=path_where_recordings_are_saved,
        metadata_file_name=metadata_file_name,
    )

    recording_ids = get_audio_ids(recording_metadata)
    formatted_cookies = format_cookies_for_request(cookies)
    download_wav_files(
        audio_ids=recording_ids,
        user_agent=user_agent,
        cookies=formatted_cookies,
        recording_path=path_where_recordings_are_saved,
    )

    print_log(f"Finished downloading all recordings for user {username}.")

    driver.quit()


def get_recordings_for_all_users(
    driver_location: str,
    show_driver: bool,
    end_date: str,
    cookies_file: str,
    config_file: str,
    info_file: str,
    output_dir: str,
    user_agent: str,
    user: Optional[str],
    download_duplicates: bool = False,
    system: str = "linux",
) -> None:
    """
    Runs the recording script for all users. If one user errors out, then the script will record the error
    for that user in the correct subdirectory and will move on to the next users.
    The number of users (and their usernames and passwords) are specified in the config file.

    :param driver_location: Location of the WebDriver.
    :param show_driver: Whether to show the driver or run it in the background.
    :param end_date: The earliest date to search for recordings from. The date range of recordings will be from
        this date to the date the script is ran on.
    :param cookies_file: The file location of the previous cookies (if any).
    :param config_file: The credentials file which stores the usernames and passwords for users.
    :param info_file: The file where the recording metadata will be saved.
    :param output_dir: The folder / directory where the recording wav files will be saved.
    :param download_duplicates: Whether the script should find the metadata for recordings that already exist
        within the config file or not.
    :param user: A specific user to run this script for.
    :param user_agent: The user agent of the driver.
    :param system: The OS where the script is running.

    :return: None.
    """
    credentials = load_credentials(credentials_file=config_file, user=user)
    total_users = len(credentials)
    today_date = get_today_date_mm_dd_yyyy()
    error_file_name = "errors.json"
    output_dir_name = output_dir.split("/")[-1]

    for i, credentials_for_one_user in enumerate(credentials):
        web_driver = create_driver(
            user_agent=user_agent,
            show=show_driver,
            system=system,
            driver_location=driver_location,
        )
        username = credentials_for_one_user["username"]
        password = credentials_for_one_user["password"]
        print_log(f"Working on user #{i+1}: {username} (out of {total_users} users).")
        path_where_recordings_are_saved = get_recording_path(
            date=today_date, output_folder=output_dir_name, username=username
        )
        try:
            get_recordings(
                driver=web_driver,
                end_date=end_date,
                cookies_file=cookies_file,
                username=username,
                password=password,
                info_file=info_file,
                user_agent=user_agent,
                download_duplicates=download_duplicates,
                system=system,
                path_where_recordings_are_saved=path_where_recordings_are_saved,
            )
        except Exception as e:
            print_log(
                f"ERROR: The script has errored out for user {username}. These recordings will be skipped. "
                f"You can check the error file ({error_file_name}) for all errors."
            )
            error_dict = {
                username: {
                    "error message": str(e),
                    "full stack message": get_full_stack(),
                }
            }
            save_errors(
                errors=error_dict,
                recording_path=path_where_recordings_are_saved,
                error_file_name=error_file_name,
            )

        print("\n")


@click.command()
@click.option(
    "-c",
    "--config",
    type=str,
    help="specify a file for credential information",
    required=False,
    default="credentials.json",
)
@click.option(
    "-i",
    "--info",
    type=str,
    help="specify a file for the recording info",
    required=False,
    default="recordinginfo.json",
)
@click.option(
    "-C",
    "--cookies",
    type=str,
    help="specify a file for the stored cookies",
    required=False,
    default="cookies.json",
)
@click.option(
    "-o",
    "--output",
    type=str,
    help="specify a directory to output files",
    required=False,
    default="recordings",
)
@click.option(
    "-d",
    "--date",
    type=str,
    help="specify a date in the format 'YYYY/MM/DD HH:MM:SS'",
    required=True,
)
@click.option(
    "--system",
    type=click.Choice(["linux", "mac"], case_sensitive=False),
    required=False,
    default="linux",
    help="Specify the OS you are working on (linux or mac)",
)
@click.option(
    "--show", is_flag=True, help="show the chrome window as it searches for recordings."
)
@click.option(
    "--download-duplicates",
    is_flag=True,
    help="download recordings that have already been downloaded.",
)
@click.option("--driver", type=str, help="Specify file location of driver.")
@click.option(
    "--user",
    type=str,
    help="Specify a single user to be run from the config file.",
    required=False,
)
def main(
    config: str,
    info: str,
    cookies: str,
    output: str,
    date: str,
    system: str,
    show: bool,
    download_duplicates: bool,
    driver: str,
    user: str,
) -> None:
    """
    This script takes a list of credentials from the credentials file and downloads all recordings from a certain
    date to today for each user.

    The recording information is downloaded as well as the actual file. Each recording and information is put
    into its own subdirectory.

    This script can run on mac or linux.
    """

    show = False if show is None else show
    download_duplicates = False if download_duplicates is None else download_duplicates
    user_agent = create_user_agent()

    ensure_file_existence(config)

    get_recordings_for_all_users(
        driver_location=driver,
        show_driver=show,
        end_date=date,
        cookies_file=cookies,
        config_file=config,
        info_file=info,
        output_dir=output,
        user_agent=user_agent,
        download_duplicates=download_duplicates,
        system=system,
        user=user,
    )


if __name__ == "__main__":
    main()
