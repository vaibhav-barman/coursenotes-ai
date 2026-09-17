from selenium import webdriver

def setup():
    driver = webdriver.Chrome()
    return driver