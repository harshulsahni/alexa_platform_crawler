import datetime
import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import sys
import traceback

from fake_useragent import UserAgent
from selenium.webdriver.chrome.webdriver import WebDriver


def raise_exception(e: Exception, driver: WebDriver) -> None:
    """
    Raises exception and quits driver. This helps prevent against the Chrome window still being open after
    certain errors pass.

    :param e: Exception to raise.
    :param driver: The WebDriver.

    :return: None.
    """
    driver.quit()
    raise e


def print_log(message: str, input_flag: bool = False) -> Optional[str]:
    """
    Prints a log statement with the date and time before the message.

    :param message: Message to print.
    :param input_flag: Whether there is input needed by the user or not.

    :return: The input if the input was needed. Else, None.
    """
    if input_flag:
        return input(
            f"{datetime.datetime.today().strftime('%Y-%m-%d %I:%M:%S')} | INPUT NEEDED: {message}"
        )
    else:
        print(f"{datetime.datetime.today().strftime('%Y-%m-%d %I:%M:%S')} | {message}")


def format_date_year_month_day(date: str) -> Tuple[str, str, str]:
    """
    Takes a date which is in month/day/year format and splits it into the three entities.

    :param date: Date as a string, represented as "month/day/year".

    :return: A tuple of the year, month, and day.
    """
    month, day, year = date.split("/")
    return year, month, day


def ensure_file_existence(file_path: str) -> None:
    """
    Ensures that the file location can be found. Returns an error if not.

    :param file_path: A string representing the file path.

    :return: None.
    """
    if not os.path.isfile(file_path):
        raise OSError(
            "Error: the file {} does not exist. Please check the path".format(file_path)
        )


def dump_cookies(cookie_file: str, cookies: List[Dict[str, Any]]) -> None:
    """
    Outputs cookies into the file specified.

    :param cookie_file: Path to the file of cookies.
    :param cookies: Cookies to output.

    :return: None.
    """
    print_log("Dumping any other new cookies.")
    with open(cookie_file, "w+") as f:
        json.dump(cookies, f, indent=4)


def get_uid_from_event(e: Dict[str, Any]) -> str:
    """
    Gets the audio ID from the network event.

    :param e: Network event represented as a dict containing network information.

    :return: The audio ID, as a string.
    """
    url = e.get("params").get("response").get("url")
    unquoted_url = urllib.parse.unquote(url)
    if "=" not in unquoted_url:
        return unquoted_url
    else:
        audio_id = unquoted_url.split("=")[-1]
        return audio_id


def get_old_metadata(metadata_info_filepath: Optional[str]) -> List[Dict[str, Any]]:
    """
    Get the metadata from the metadata file specified.

    :param metadata_info_filepath: Location of the metadata file. If None, then an empty
        metadata template will be returned.

    :return: List of metadata for all recordings that were previously downloaded.
    """
    if (
        not os.path.exists(metadata_info_filepath)
        or metadata_info_filepath
        not in Path(os.path.dirname(metadata_info_filepath)).iterdir()
    ):
        print_log("Previous metadata file not found.")
        return json.loads("[\n\n]")
    else:
        with open(metadata_info_filepath, "r") as f:
            return json.load(f)


def get_audio_ids(metadata: List[Dict[str, Any]]) -> List[str]:
    """
    Gets the audio IDs from the list of metadata information for all recordings.

    :param metadata: All metadata information for the recordings.

    :return: A list of the audio IDs.
    """
    ids = []
    for data in metadata:
        audio_id = data.get("audio_id")
        if audio_id is not None:
            ids.append(audio_id)
    return ids


def format_cookies_for_request(cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Correctly formats the WebDriver's cookies to be used to parse a network request to amazon.com.

    :param cookies: A list of driver cookies.

    :return: A dictionary of the cookies, correctly formatted.
    """
    formatted_cookies = {}
    for cookie in cookies:
        formatted_cookies.update({cookie["name"]: cookie["value"]})
    return formatted_cookies


def create_user_agent() -> str:
    """
    Creates a random user agent.

    :return: A string representing the user agent.
    """
    ua = UserAgent()
    return ua.random


def load_credentials(
    credentials_file: str, user: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Loads all of the credentials from the credentials file.

    :param credentials_file: File path of the file with all credentials.
    :param user: Optional user to filter the credentials for. If not None, then the function will
        only return credentials for that user.

    :return: A list of credentials.
    """
    with open(credentials_file, "r") as creds:
        credentials = json.load(creds)
    if user is not None:
        for user_credentials in credentials:
            for username in user_credentials.items():
                if username == user:
                    return [user_credentials]

        # else, no user can be found with that email. raise an error.
        raise ValueError(
            f'ERROR: The user "{user}" cannot be found in the credentials. Please double check '
            f"this username with the usernames in the credentials file."
        )
    else:
        return credentials


def get_today_date_mm_dd_yyyy() -> str:
    """
    Returns today's date in mm-dd-YYYY format.

    :return: Today's date.
    """
    return time.strftime("%m/%d/%Y")


def get_full_stack() -> str:
    """
    Gets the full stack trace of a program when it raises an exception.

    :return: The full stack error.
    """
    exc = sys.exc_info()[0]
    if exc is not None:
        f = sys.exc_info()[-1].tb_frame.f_back
        stack = traceback.extract_stack(f)
    else:
        stack = traceback.extract_stack()[:-1]

    traceback_line = "Traceback (most recent call last):\n"
    stackstr = traceback_line + "".join(traceback.format_list(stack))
    if exc is not None:
        stackstr += "  " + traceback.format_exc().lstrip(traceback_line)
    return stackstr


def find_last_recording_folder(current_recording_directory: str) -> Optional[str]:
    current_recording_directory = (
        current_recording_directory[:-1]
        if current_recording_directory.endswith("/")
        else current_recording_directory
    )

    date_folder, iteration = current_recording_directory.rsplit("/", 1)

    iteration_num = int(iteration)

    if iteration_num > 0:
        previous_iteration = iteration_num - 1
        return os.path.join(date_folder, str(previous_iteration))
    else:
        user_folder, date = date_folder.rsplit("/", 1)
        user_path = Path(user_folder)
        sorted_dates = sorted([d for d in user_path.iterdir() if str(d) < date])
        if len(sorted_dates) <= 0:
            return None
        else:
            previous_date = str(sorted_dates[-1])
            return os.path.join(user_folder, previous_date)


def verify_input_date(date: Any) -> bool:
    """
    Verifies that the input date is of the correct format:
    "YYYY/MM/DD HH:MM:SS"
    and is a str.

    :param date: Input date to check.

    :return: True if the date is of the correct format; False if not.
    """
    if not isinstance(date, str):
        return False

    if " " not in date:
        return False

    verify_date = re.search("[0-9]{4}/[0-9]{2}/[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", date)
    return True if verify_date else False

