import datetime
import json
import os
import re
import urllib.parse
from typing import List, Dict, Any, Tuple, Optional

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
        return input(f"{datetime.datetime.today().strftime('%Y-%m-%d %I:%M:%S')} | INPUT NEEDED: {message}")
    else:
        print(f"{datetime.datetime.today().strftime('%Y-%m-%d %I:%M:%S')} | {message}")


def format_date_year_month_day(date: str) -> Tuple[str, str, str]:
    """
    Takes a date which is in month/day/year format and splits it into the three entities.

    :param date: Date as a string, represented as "month/day/year".

    :return: A tuple of the year, month, and day.
    """
    month, day, year = date.split('/')
    return year, month, day


def ensure_file_existence(file_path: str) -> None:
    """
    Ensures that the file location can be found. Returns an error if not.

    :param file_path: A string representing the file path.

    :return: None.
    """
    if not os.path.isfile(file_path):
        raise OSError('Error: the file {} does not exist. Please check the path'.format(file_path))


def dump_cookies(cookie_file: str, cookies: List[Dict[str, Any]]) -> None:
    """
    Outputs cookies into the file specified.

    :param cookie_file: Path to the file of cookies.
    :param cookies: Cookies to output.

    :return: None.
    """
    print_log('Dumping any other new cookies.')
    with open(cookie_file, "w+") as f:
        json.dump(cookies, f, indent=4)


def get_uid_from_event(e: Dict[str, Any]) -> str:
    """
    Gets the audio ID from the network event.

    :param e: Network event represented as a dict containing network information.

    :return: The audio ID, as a string.
    """
    url = e.get('params').get('response').get('url')
    unquoted_url = urllib.parse.unquote(url)
    if '=' not in unquoted_url:
        return unquoted_url
    else:
        audio_id = unquoted_url.split('=')[-1]
        return audio_id


def get_old_metadata(metadata_info_filepath: str) -> List[Dict[str, Any]]:
    """
    Get the metadata from the metadata file specified.

    :param metadata_info_filepath: Location of the metadata file.

    :return: List of metadata for all recordings that were previously downloaded.
    """
    if not os.path.exists(metadata_info_filepath) or metadata_info_filepath not in os.listdir():
        print_log("Metadata file not found. Creating a new one.")
        with open(metadata_info_filepath, 'w+') as f:
            f.write("[\n\n]")
    with open(metadata_info_filepath, 'r') as f:
        metadata = json.load(f)
    return metadata


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
