import browser


driver = browser.setup()

driver.get("https://www.selenium.dev/selenium/web/web-form.html")

input("Press Enter to close the browser...")

driver.quit()