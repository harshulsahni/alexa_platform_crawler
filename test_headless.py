#!/usr/bin/env python3

from fake_useragent import UserAgent
from pyvirtualdisplay import Display
from selenium import webdriver

chrome_options = webdriver.ChromeOptions()
display = Display(visible=False, size=(1200, 600)).start()


ua = UserAgent()
userAgent = ua.random
print(userAgent)
chrome_options.add_argument("user-agent=" + str(userAgent))
#chrome_options.add_argument("--headless")
chrome_options.add_experimental_option("detach", True)

driver = webdriver.Chrome(executable_path="/usr/local/bin/chromedriver", options=chrome_options)
driver.get("https://intoli.com/blog/making-chrome-headless-undetectable/chrome-headless-test.html")

with open("headlesstest.html", "w") as f:
    f.write(driver.page_source)
    f.close()

driver.quit()
display.stop()
