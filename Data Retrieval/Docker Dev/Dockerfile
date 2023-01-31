FROM python:slim

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
#COPY app.py /usr/src/app/ => bind mount nel compose

RUN python3 -m venv venv && . venv/bin/activate

RUN pip install --no-cache-dir flask pymongo

ENV FLASK_APP=data-retrieval.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000
ENV FLASK_ENV=development

ENTRYPOINT ["flask", "run"]
