FROM python:slim

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY data-retrieval.py .

RUN python3 -m venv venv && . venv/bin/activate

RUN pip install --no-cache-dir flask pymongo

ENV FLASK_APP=data-retrieval.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

STOPSIGNAL SIGINT

ENTRYPOINT ["flask", "run"]
