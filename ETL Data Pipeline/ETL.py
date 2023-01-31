
import ETL_BL
import threading
import time
import schedule
import os

from prometheus_client import start_http_server

def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    job_thread.start()

schedule.every(1).hours.do(run_threaded, ETL_BL.everyHour)
schedule.every(2).minutes.do(run_threaded, ETL_BL.everyY)

# Li facciamo partire subito
run_threaded(ETL_BL.everyHour)
run_threaded(ETL_BL.everyY)

if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(8008)
    print("Server http prometheus exporter started")

while True:
    schedule.run_pending()
    time.sleep(1)