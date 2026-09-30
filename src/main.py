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
    print(f"  {item['name']}")
    print(f"  {item['url']}")
    print()

# Open the first course (Modern Databases)
course.open_course(driver, courses[0])

print(f"\nOpened course: {courses[0]['name']}")

# --- Phase 1: Discover modules and their lecture/reading links ---

print("\nDiscovering modules...")

modules = course.get_modules(driver)

if not modules:
    print("ERROR: No modules found. The page may not have loaded correctly.")
    input("Press Enter to close the browser...")
    driver.quit()
    raise SystemExit(1)

print(f"Found {len(modules)} modules.\n")

# Visit each module page and collect its content items
all_items = []

for mod in modules:
    items = course.get_module_items(driver, mod)

    lectures = [i for i in items if i["type"] == "lecture"]
    readings = [i for i in items if i["type"] == "reading"]

    print(f"\n  Module {mod['number']}: {mod['name']}")
    print(f"  {len(lectures)} lecture(s), {len(readings)} reading(s)")

    for item in items:
        type_label = "📹 Lecture" if item["type"] == "lecture" else "📄 Reading"
        print(f"    [{type_label}] {item['title']}")
        print(f"             {item['url']}")

    all_items.append({
        "module": mod,
        "items": items,
    })

# Summary
total_lectures = sum(
    len([i for i in block["items"] if i["type"] == "lecture"])
    for block in all_items
)
total_readings = sum(
    len([i for i in block["items"] if i["type"] == "reading"])
    for block in all_items
)

print(f"\n--- Discovery complete ---")
print(f"Modules : {len(modules)}")
print(f"Lectures: {total_lectures}")
print(f"Readings: {total_readings}")

input("\nPress Enter to close the browser...")

driver.quit()