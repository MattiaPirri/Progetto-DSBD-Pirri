FROM python:slim

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN python3 -m venv venv && . venv/bin/activate

RUN pip install --no-cache-dir flask pymongo grpcio grpcio-tools grpcio-reflection prometheus_api_client

ENV FLASK_APP=sla-manager.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000
ENV FLASK_ENV=development

ENTRYPOINT ["python", "sla-manager.py"]

