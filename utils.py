import datetime
import re
import os


def raise_exception(e, driver):
    driver.quit()
    raise e


def print_log(message, input_flag=False):
    if input_flag:
        input(f"{datetime.datetime.today().strftime('%Y-%m-%d %I:%M:%S')} | INPUT NEEDED: {message}")
    else:
        print(f"{datetime.datetime.today().strftime('%Y-%m-%d %I:%M:%S')} | {message}")


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


def get_file_path(name, directory, extension):
    if not os.path.exists(directory + "/" + name + "." + extension):
        return directory + "/" + name + "." + extension
    else:
        i = 1
        while os.path.exists(str(directory + "/" + name + "_%s" + "." + extension) % i):
            i += 1
        return str(directory + "/" + name + "_%s" + "." + extension) % i


def ensure_file_existence(file_path):
    if not os.path.isfile(file_path):
        raise OSError('Error: the file {} does not exist. Please check the path'.format(file_path))
