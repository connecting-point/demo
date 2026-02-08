
CREATE TABLE IF NOT EXISTS admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100),
    password VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS employees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    mobile VARCHAR(20),
    email VARCHAR(100),
    address TEXT,
    aadhaar VARCHAR(20),
    aadhaar_photo VARCHAR(255),
    username VARCHAR(50),
    password VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT,
    photo VARCHAR(255),
    latitude VARCHAR(50),
    longitude VARCHAR(50),
    timestamp DATETIME
);

INSERT INTO admin (username, password) VALUES ('admin', 'admin123');
