import browser
import coursera
import course


driver = browser.setup()

print("Opening Coursera...")

coursera.open_coursera(driver)

print("Coursera opened.")

input("Log in if necessary, then press Enter...")

print("Starting course scraping...")

courses = course.get_course_links(driver)

print(f"Found {len(courses)} courses.")

for item in courses:

    print(item["name"])
    print(item["url"])
    print()

input("Press Enter to close the browser...")

driver.quit()