FROM python:3.9-slim-bullseye
RUN pip install prometheus_api_client confluent-kafka grpcio grpcio-tools schedule prometheus-client statsmodels scikit-learn

WORKDIR /file/
ADD . .
CMD ["python", "ETL.py"]
