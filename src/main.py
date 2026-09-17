import browser
import coursera


driver = browser.setup()

coursera.open_coursera(driver)

input("Press Enter to close the browser...")

driver.quit()