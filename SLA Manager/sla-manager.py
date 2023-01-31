from flask import Flask, request
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.json_util import dumps
from bson.objectid import ObjectId
import os
import threading
import json
import grpc
import sla_pb2
import sla_pb2_grpc
from concurrent import futures
from grpc_reflection.v1alpha import reflection
import sys
import pandas as pd
from io import StringIO

### PROMETHEUS
from prometheus_api_client import PrometheusConnect, MetricsList, MetricSnapshotDataFrame, MetricRangeDataFrame
from datetime import timedelta, datetime
from prometheus_api_client.utils import parse_datetime
from itertools import groupby

prom_url = "http://" + os.environ["PROMETHEUS"] + ":" + os.environ["PROMETHEUS_PORT"]
#prom_url = "http://prom:9090"
prom = PrometheusConnect(url=prom_url, disable_ssl=True)

# Ritorna pandas dataframe della metrica della durata passata come secondo argomento
def getMetric(name, duration):   
    start_time = parse_datetime(duration) - timedelta(minutes=2) # prendiamo 2 minuti in più
    end_time = parse_datetime("now")
    metric_name = name['__name__']
    label_config = name.copy()
    del label_config['__name__']
    # Ottengo le metriche da prometheus
    try:
        metric_data = prom.get_metric_range_data(
            metric_name=metric_name,
            label_config=label_config,
            start_time=start_time,
            end_time=end_time,
        )
    except Exception as err:
        print("Errore di connessione: {}".format(err), file=sys.stderr)
    return MetricRangeDataFrame(metric_data)

def getViolationIntervals(df, min_, max_):
    return [list(g) for k, g in groupby((df['value'] > max_) | (df['value'] < min_))]

def getViolationResult(df, min_, max_, for_, return_violations=False):
    violation_intervals = getViolationIntervals(df, min_, max_)

    violations = {"n": 0, "time": 0}
    violations_list = []

    index = 0

    for list in violation_intervals:
        if True in list:
            violation = {}
            violation['start_time'] = df.index[index]
            violation['end_time'] = df.index[index+len(list)-1]
            violation['duration'] = violation['end_time'] - violation['start_time']
            violation['start_time'] = str(violation['start_time'])
            violation['end_time'] = str(violation['end_time'])
            violation['duration'] = violation['duration'].seconds/60
            print(violation['duration'])
            # Violazione effettiva
            if violation['duration'] >= for_:
                if len(list) != 1:
                    violation['avg_value'] = df['value'].iloc[index:index+len(list)-1].mean()
                    violation['max_value'] = df['value'].iloc[index:index+len(list)-1].max()
                    violation['min_value'] = df['value'].iloc[index:index+len(list)-1].min()
                else:
                    violation['avg_value'] = violation['max_value'] = violation['min_value'] = df['value'].iloc[index]
                if return_violations == True: 
                    violations_list.append(violation)
                violations['n'] = violations['n'] + 1
                violations['time'] = violations['time'] + violation['duration']   
        index = index + len(list)
    if return_violations == True:
        return violations, violations_list
    else:
        return violations
### FINE PROMETHEUS ###

###
class SlaService(sla_pb2_grpc.SlaServiceServicer):

    def GetSLASet(self, request, context):
        sla_set = list(sla.find({}, {"_id": 0, "name": 1}))
        sla_set_names = list(map(lambda ele: ele['name'], sla_set))
        #print(sla_set_names)
        for name in sla_set_names:
            #print(name)
            seasonality = metrics.find_one({"name": name}, {"_id": 0, "metadata": 1})
            #print(seasonality)
            s = None
            if seasonality:
                if "add" in seasonality['metadata']['seasonality'] and "mul" in seasonality['metadata']['seasonality']:
                    s = sla_pb2.SLASetResponse.Seasonality(
                        add = seasonality['metadata']['seasonality']['add']['period'],
                        mul = seasonality['metadata']['seasonality']['mul']['period']
                    )
                #print(s)
            yield sla_pb2.SLASetResponse(metric=name, seasonality=s)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    sla_pb2_grpc.add_SlaServiceServicer_to_server(SlaService(), server)

    SERVICE_NAMES = (
        sla_pb2.DESCRIPTOR.services_by_name['SlaService'].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)

    port = os.environ['GRPC_PORT']
    server.add_insecure_port('[::]:' + port)
    server.start()
    print("[gRPC] SlaService started, listening on " + port)
    server.wait_for_termination()


app = Flask(__name__)

mongo_uri = str("mongodb://" +
                os.environ['MONGO_USERNAME'] + ":" +
                os.environ['MONGO_PASSWORD'] + "@" +
                os.environ['MONGO_SERVER'] + "/"
            )

client = MongoClient(mongo_uri)
# Verifichiamo che il server mongod sia up
try:
    client.admin.command('ping')
except ConnectionFailure:
    print("Server not available")

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

@app.route("/slaset", methods=['GET'])
def slaset():
    try:
        client.admin.command('ping')
    except:
        return "DB not available", 504
    return dumps(sla.find({}))

@app.route("/slaset", methods=['PUT'])
def slaset_put(): # TODO controllare che non venga inserita una metrica più di una volta
    try:
        client.admin.command('ping')
    except:
        return "DB not available", 504
    # Controlliamo se la richiesta è effettuata correttamente (5 metriche con max e min e durata) ed esistenti nel sistema
    if len(request.json) != 5: 
        return "SLA set must consist of 5 metrics. {} provided".format(len(request.json)), 400
    stringa = ""
    for elem in request.json:
        metric = metrics.find_one({"name": elem['name']})
        if metric == None:
            stringa = stringa + "- The metric {} does not exists;\n".format(elem['name'])
        elif 'range' in elem:
            if 'min' not in elem['range']:
                stringa = stringa + "- Minimum value of range not provided for {};\n".format(elem['name'])
            if 'max' not in elem['range']:
                stringa = stringa + "- Maximum value of range not provided for {};\n".format(elem['name'])
            if elem['range']['min'] > elem['range']['max']:
                stringa = stringa + "- Invalid range provided [minimum given value ({}) is greater than maximum one ({})] for {};\n".format(elem['range']['min'], elem['range']['max'], elem['name'])
        else:
            stringa = stringa + "- Range not provided for {};\n".format(elem['name'])
        # Controlliamo se viene fornita la durata (un numero intero di minuti) 
        if 'for' in elem:
            if not isinstance(elem['for'], int):
                stringa = stringa + "- Invalid duration (for key) provided for {};\n".format(elem['name'])
        else:
            stringa = stringa + "- Duration (for key) not provided for {};\n".format(elem['name'])

    if len(stringa) != 0:
        return stringa, 400   

    message = "SLA set created"
    statusCode = 201
    # Se il set era gia stato definito
    if sla.count_documents({}) > 0:
        statusCode = 200
        message = "SLA set updated"
        if not sla.delete_many({}).acknowledged:
            return "Error on db", 500

    if not sla.insert_many(request.json).acknowledged:
        return "Error on db", 500
    return message, statusCode

@app.route("/status")
def status():
    try:
        client.admin.command('ping')
    except:
        return "DB not available", 504
    sla_set = list(sla.find({}))
    # Se lista vuota
    if not sla_set:
        return "Sla set not defined", 400
    actual_status = []
    for sla_elem in sla_set:
        actual_status_elem = {}
        actual_status_elem['name'] = sla_elem['name']
        df = getMetric(sla_elem['name'], str(sla_elem['for'])+"m")
        violation_intervals = getViolationIntervals(df, sla_elem['range']['min'], sla_elem['range']['max'])
        metric_status = "inactive"
        description = "Actual value [{}] in ({}, {})".format(df.iloc[-1]['value'], sla_elem['range']['min'], sla_elem['range']['max'])
        last_three_values = df.tail(3)['value'].tolist()
        if True in violation_intervals[-1]:
            violation_time = df.index[-1] - df.index[-len(violation_intervals[-1])] 
            violation_time = violation_time.seconds/60 + 1
            metric_status = "pending"
            description = "Service level agreement violated for {:.2f}/{} min ({:.2%}), last three values {} not in ({}, {})".format(violation_time, sla_elem['for'],violation_time/sla_elem['for'], last_three_values, sla_elem['range']['min'], sla_elem['range']['max'])
            if violation_time >= sla_elem['for']:
                description = "Service level agreement violated for more than {} min, last three values {}, allowed range: ({}, {})".format(sla_elem['for'], last_three_values, sla_elem['range']['min'], sla_elem['range']['max'])
                metric_status = "firing"
        actual_status_elem['status'] = metric_status
        actual_status_elem['description'] = description
        actual_status_elem['last-values'] = last_three_values
        actual_status.append(actual_status_elem)
    return json.dumps(actual_status)


@app.route("/violations")
def violations():
    try:
        client.admin.command('ping')
    except:
        return "DB not available", 504

    sla_set = list(sla.find({}))
    # Se lista vuota
    if not sla_set:
        return "SLA set not defined", 400
    result = []
    for sla_elem in sla_set:
        violations = {}
        violations['name'] = sla_elem['name']
        df = getMetric(sla_elem['name'], "12h")
        # Un ora
        df_1h = df.last("61min")
        violations['1h'] = getViolationResult(df_1h, sla_elem['range']['min'], sla_elem['range']['max'], sla_elem['for'])
        # Tre ore
        df_3h = df.last("181min")
        violations['3h'] = getViolationResult(df_3h, sla_elem['range']['min'], sla_elem['range']['max'], sla_elem['for'])
        violations['12h'], violations['violation_list'] = getViolationResult(df, sla_elem['range']['min'], sla_elem['range']['max'], sla_elem['for'], return_violations=True)
        result.append(violations)
    return json.dumps(result)


@app.route("/future-violations")
def future_violations():
    try:
        client.admin.command('ping')
    except:
        return "DB not available", 504
    sla_set = list(sla.find({}))
    # Se lista vuota
    if not sla_set:
        return "SLA set not defined", 400
    result = []
    actual_time = datetime.now()
    for sla_elem in sla_set:
        # Recupero i valori predetti per concatenarli alla serie reale
        prediction = metrics.find_one({"name": sla_elem['name']}, {"_id":0, "prediction": 1})
        # Se non c'è la predizione
        if not prediction:
            result_elem = {}
            result_elem['name'] = sla_elem['name']
            result_elem['error'] = "Prediction not available"
        else: 
            result_elem = {}
            result_elem['name'] = sla_elem['name']
            colnames=['Timestamp', 'value'] 
            prediction_df = pd.read_csv(StringIO(prediction['prediction']['values']), header=0, names=colnames, parse_dates=[0], dayfirst=True, index_col=0)
            # Recupero la metrica reale. Sono interessato ad ottenere al più un numero di campioni pari alla durata della violazione
            df = getMetric(sla_elem['name'], str(sla_elem['for'])+"m")
            # prendere i campioni successivi all'ultimo reale
            last_sample_time = df['value'].index[-1]
            prediction_df = prediction_df.loc[last_sample_time:]
            # Unire le due dataframe
            df =pd.concat([df, prediction_df])
            print(df['value'])

            violation_intervals = getViolationIntervals(df, sla_elem['range']['min'], sla_elem['range']['max'])
            violations_list = []
            index = 0
            for list_ in violation_intervals:
                if True in list_:
                    violation = {}
                    violation['start_time'] = df.index[index]
                    violation['end_time'] = df.index[index+len(list_)-1]
                    if violation['end_time'] > actual_time:
                        violation['duration'] = violation['end_time'] - violation['start_time']
                        violation['duration'] = violation['duration'].seconds/60 + 1
                        print(violation['duration'])
                        # firing
                        if violation['duration'] >= sla_elem['for']:
                            if violation['start_time'] < actual_time: #era pending o già firing
                                duration_in_future = violation['end_time'] - actual_time
                                if violation['duration'] - duration_in_future.seconds/60 >= sla_elem['for']:
                                    # era firing
                                    violation['description'] = "Was already firing, continuing firing"
                                else:
                                    # era pending
                                    violation['description'] = "Was pending, will fire"
                            else:
                                violation['description'] = "Will fire"
                        # pending
                        else:
                            violation['description'] = "Will be pending"

                        if len(list_) != 1:
                            violation['avg_value'] = df['value'].iloc[index:index+len(list_)-1].mean()
                            violation['max_value'] = df['value'].iloc[index:index+len(list_)-1].max()
                            violation['min_value'] = df['value'].iloc[index:index+len(list_)-1].min()
                        else:
                            violation['avg_value'] = violation['max_value'] = violation['min_value'] = df['value'].iloc[index]
                        violation['start_time'] = str(violation['start_time'])
                        violation['end_time'] = str(violation['end_time'])
                        violations_list.append(violation)

                index = index + len(list_)        
            result_elem['violations'] = violations_list
            result_elem['prediction_rmse'] = prediction['prediction']['rmse']
        result.append(result_elem)
    return json.dumps(result)  
        
        



if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)).start()
    #app.run(host="0.0.0.0", port=5000)
    serve()