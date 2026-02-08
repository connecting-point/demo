import sqlite3
from datetime import datetime

# Step 1: Connect to the database
conn = sqlite3.connect("employees.db")
cursor = conn.cursor()

# Step 2: Prepare values
employee_id = 1  # change this to a valid ID from your employees table
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
action = "IN"
latitude = "10.1234"
longitude = "76.5432"
subject = "Site inspection"

# Step 3: Photo filenames (these should be actual filenames from static/attendance_photos/)
photo_filenames = ['test1.jpg', 'test2.jpg']
photo_paths = ",".join(photo_filenames)  # turns into: "test1.jpg,test2.jpg"

# Step 4: Insert into the database
cursor.execute("""
    INSERT INTO attendance (employee_id, timestamp, action, latitude, longitude, subject, photo_paths)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (employee_id, timestamp, action, latitude, longitude, subject, photo_paths))

# Step 5: Commit and close
conn.commit()
conn.close()

print("✅ Attendance record inserted with multiple photos!")
