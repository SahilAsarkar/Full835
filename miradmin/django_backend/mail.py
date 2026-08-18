import smtplib

SMTP_HOST = "smtp.ionos.com"
SMTP_PORT = 587

EMAIL = "akshay.kumar@onesmarter.com"
PASSWORD = "ewXtLJrSPXUdhubnMtMUT9xXFZ73uwHz"

try:
    print("Connecting to IONOS SMTP server...")

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)

    print("Starting TLS...")
    server.starttls()

    print("Logging in...")
    server.login(EMAIL, PASSWORD)

    print("SMTP connection successful!")
    print("IONOS email login successful!")

    server.quit()

except Exception as e:
    print("SMTP connection failed!")
    print("Error:", e)