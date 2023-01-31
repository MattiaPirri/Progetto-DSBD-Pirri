import os
from confluent_kafka import Consumer, KafkaException
import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import time

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

# Selezioniamo il db e la collezione
db = client.db
metrics = db.metrics

# Prepariamo il consumer kafka
c = Consumer({
    'bootstrap.servers': os.environ['KAFKA_BROKER'],
    'group.id': 'data-storage',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False
})

# Ci iscriviamo al topic
while True:
    try:
        c.subscribe([os.environ['KAFKA_TOPIC']])
        print("Subscribe ok")
        break
    except KafkaException as ke:
        if not(ke.args[0].retriable()):
            print("Non retriable error!")
            exit(1)
        print("Retriable error!")
        time.sleep(5)



try:
    while True:
        msg = c.poll(1.0)
        # poll ritorna None se non ci sono messaggi nel topic
        if msg is None:
            print("Waiting for message or event/error in poll()")
            continue
        elif msg.error():
            print('error: {}'.format(msg.error()))
        else:
            # Check for Kafka message
            record_value = msg.value()
            data = json.loads(record_value)
            print("Received message: {}\n{}\n".format(record_value, data))
            filtro = {"name" : {'$eq': data['name']}}
            # Se non è una metrica del set SLA
            if 'prediction' not in data and 'metadata' not in data:
                # Ripuliamo i campi (ci serve nel caso di UPDATE del set)
                value = {"$set": data, "$unset": {"prediction": ""}}
            else:
                value = {"$set": data}
            try:
                client.admin.command('ping')
                # Quando il db è disponibile eseguiamo l'upsert e il commit della lettura su kafka
                metrics.update_one(filtro, value, upsert=True)
                offset = c.commit(asynchronous=False)
                print(offset)
            except ConnectionFailure:
                print("Server not available")
                # Per far si che il prossimo messaggio sia l'ultimo committato e non il prossimo precaricato
                c.unsubscribe()
                c.subscribe([os.environ['KAFKA_TOPIC']])
            
# Catturiamo l'eccezione (per prendere lo stop_signal: SIGINT indicato nel compose)
except KeyboardInterrupt:
    pass
finally:
    # Leave group and commit final offsets
    c.close()
