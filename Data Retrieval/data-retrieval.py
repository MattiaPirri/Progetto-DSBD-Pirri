from flask import Flask
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.json_util import dumps
from bson.objectid import ObjectId
import os

app = Flask(__name__)

mongo_uri = str("mongodb://" +
                os.environ['MONGO_USERNAME'] + ":" +
                os.environ['MONGO_PASSWORD'] + "@" +
                os.environ['MONGO_SERVER']
            )
print(mongo_uri)

client = MongoClient(mongo_uri)
# Verifichiamo che il server mongod sia up
try:
    client.admin.command('ping')
except ConnectionFailure as e:
    print("Server not available: ", e)

db = client.db
metrics = db.metrics
sla = db.sla

@app.route("/metrics")
def metric_list():
    try:
        client.admin.command('ping')
    except:
        return "DB not available", 504
    return dumps(metrics.find({}, {"name": 1}))

@app.route("/metrics/<id>/metadata")
def metadata(id):
    try:
        client.admin.command('ping')
    except:
        return "DB not available", 504
    metric = metrics.find_one({"_id": ObjectId(id)}, {"_id": 0, "metadata": 1})
    if metric == None:
        return "Invalid metric id or no metadata found for given id", 400
    return dumps(metric)

@app.route("/metrics/<id>/values")
def values(id):
    try:
        client.admin.command('ping')
    except:
        return "DB not available", 504
    metric = metrics.find_one({"_id": ObjectId(id)}, {"_id": 0, "values": 1})
    if metric == None:
        return "Invalid metric id or no values found for given id", 400
    return dumps(metric)

@app.route("/metrics/<id>/prediction")
def prediction(id):
    try:
        client.admin.command('ping')
    except:
        return "DB not available", 504
    metric = metrics.find_one({"_id": ObjectId(id)}, {"_id": 0, "name": 1})
    if metric == None:
        return "Invalid metric id or no prediction found for given id", 400
    if sla.find_one({"name": metric['name']}) == None:
        return "Prediction not available as the metric is not part of the sla set"
    return dumps(metrics.find_one({"_id": ObjectId(id)}, {"_id": 0, "prediction": 1}))