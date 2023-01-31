FROM python:3.9-slim
RUN pip install --no-cache-dir pymongo confluent-kafka

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY data-storage.py .

STOPSIGNAL SIGINT

ENTRYPOINT ["python"]
CMD ["data-storage.py"]

