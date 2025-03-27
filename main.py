import schedule
import time
from meebezig import meebezig

meebezig()

schedule.every().day.at("00:00").do(meebezig)

while True:
    schedule.run_pending()
    time.sleep(60)
