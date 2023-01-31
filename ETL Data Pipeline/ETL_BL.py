from prometheus_api_client import PrometheusConnect, MetricsList, MetricSnapshotDataFrame, MetricRangeDataFrame
from datetime import timedelta
from prometheus_api_client.utils import parse_datetime
from confluent_kafka import Producer, KafkaError, KafkaException
import sys
import json
import os
import time

import grpc
import sla_pb2_grpc
import sla_pb2

from numpy.fft import rfft, rfftfreq
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import adfuller, acf
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing
from sklearn.metrics import mean_squared_error
#from pmdarima import auto_arima
#from statsmodels.tsa.arima.model import ARIMA,ARIMAResults
#import warnings
#warnings.filterwarnings("ignore")

from prometheus_client import Gauge

g1h = Gauge('etl_executiontime_1h', 'ETL execution time for calculating 1h values', ["metric_name"])
g3h = Gauge('etl_executiontime_3h', 'ETL execution time for calculating 3h values', ["metric_name"])
g12h = Gauge('etl_executiontime_12h', 'ETL execution time for calculating 12h values', ["metric_name"])
gMeta = Gauge('etl_executiontime_metadata', 'ETL execution time for calculating metadata', ["metric_name"])
gPre = Gauge('etl_executiontime_prediction', 'ETL execution time for calculating prediction', ["metric_name"])

conf = {'bootstrap.servers': os.environ["KAFKA_BROKER"], 'acks': 'all' }
topic = os.environ["KAFKA_TOPIC"]

try: 
    p = Producer(**conf)
    print("Connesso con successo")
except KafkaException as ke:
    print("Errore: ", ke)
print(p)


def delivery_callback(err, msg):
    if err:
        # stampiamo un errore e non riproviamo. Accettiamo di perdere un campione
        sys.stderr.write('%% Message failed delivery: %s\n' % err)
    else:
        sys.stderr.write('%% Message delivered to %s, partition[%d] @ %d\n' %
                            (msg.topic(), msg.partition(), msg.offset()))


# Usiamo le variabili di ambiente per non dover ricreare l'immagine se dovesse cambiare l'endpoint
prom_url = "http://" + os.environ["PROMETHEUS"] + ":" + os.environ["PROMETHEUS_PORT"]
prom = PrometheusConnect(url=prom_url, disable_ssl=True)

metric_name_list = ['node_filesystem_avail_bytes', 'cpuTemp', 'diskUsage', 'realUsedMem', 'networkThroughput']
label_config = {}

def everyHour():
    start_time = parse_datetime("15d") # 5 giorni nel prometheus
    end_time = parse_datetime("now")

    # Ottengo le metriche da prometheus
    for metric_name in metric_name_list:
        try:
            metric_data = prom.get_metric_range_data(
                metric_name=metric_name,
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as err:
            print("Errore di connessione: {}".format(err), file=sys.stderr)
            return

        print("Ho ricevuto i dati")
        # Controllo che il filtro "matchi" effettivamente qualche metrica
        if len(metric_data) == 0:
            # Ricostruisco il filtro come se fosse PromQL
            message = "Non è presente alcuna metrica che corrisponde al filtro: " + metric_name
            if len(label_config) > 0 :
                message = message + "{"
                for elem in label_config:
                    message = message + elem + "='" + label_config[elem] + "', "
                message = message[:-2] + "}"
            print(message)
        else:
            # Per ogni metrica ritornata dal prometheus
            for metric_data_i in metric_data:
                ris = {}
                ris['name'] = metric_data_i['metric']
                df = MetricRangeDataFrame(metric_data_i)
                df = df.dropna()

                start = time.time()
                # Se non è costante
                if df['value'].min() != df['value'].max():
                    # Stazionarietà
                    stationarity = {}
                    adft = adfuller(df['value'],autolag='AIC') 
                    stationarity['stationary'] = bool(adft[1] < 0.05)
                    stationarity['p_value'] = adft[1]
                
                    # Autocorrelazione
                    acf_res = {}
                    a, b = acf(df['value'], alpha=.05)
                    print(a)
                    for i in range(0,len(a)):
                        if a[i] <= b[i][0]-a[i] or a[i] >= b[i][1]-a[i]:
                            acf_res[i] = a[i]


                    # Stagionalità
                    seasonality = {}
                    fft_val = abs(rfft(df['value']))
                    fft_freq = rfftfreq(len(df['value']), d=1.0)
                    fft_val = fft_val[2:]
                    fft_freq = fft_freq[2:]
                    max_freq = fft_freq[np.argmax(fft_val)]
                    period = int(1/max_freq)
                    """
                    err = {}
                    # Proviamo a vedere se è effettivamente quello con errore minore. Controlliamo tutti i periodi che vanno da 
                    # poco prima della metà del periodo a poco dopo del doppio.
                    # Per ottimizzare potrebbe avere senso provare inizialmente con un passo maggiore di 1 e poi rieseguire il 
                    # ciclo a passi di 1 nell'intorno del punto con residuo minimo.
                    for i in range (int(period/2.1), min(int(period*2.1), math.floor(df['value'].size/2)), 1):
                        result = seasonal_decompose(df['value'], model='add', period=i)  # model='add' also works 
                        err[i] = result.resid.abs().max()
                        print("add errore[{}]: {}".format(i, err[i]))

                    indice = min(err, key=err.get)
                    print("min add: ", indice)
                    seasonality['add'] = {}
                    seasonality['add']['period'] = indice
                    seasonality['add']['error'] = err[indice]

                    result = seasonal_decompose(df['value'], model='add', period=indice)  # model='add' also works 
                    result.plot();
                    plt.savefig("/file/{}.png".format(add)) 
                    
                    err = {}
                    for i in range (int(period/2.1), min(int(period*2.1), math.floor(df['value'].size/2)), 1):
                        result = seasonal_decompose(df['value'], model='mul', period=i)  # model='add' also works 
                        err[i] = result.resid.subtract(1).abs().max()
                        print("mul errore[{}]: {}".format(i, err[i]))

                    indice = min(err, key=err.get)
                    print("min mul: ", indice)
                    seasonality['mul'] = {}
                    seasonality['mul']['period'] = indice
                    seasonality['mul']['error'] = err[indice]

                    result = seasonal_decompose(df['value'], model='mul', period=indice)  # model='add' also works 
                    result.plot();
                    plt.savefig("/file/{}.png".format(mul)) 
                    """
                    seasonality['add'] = {}
                    seasonality['add']['period'] = period
                    #result = seasonal_decompose(df['value'], model='add', period=period)
                    #seasonality['add']['error'] = result.resid.abs().max()

                    seasonality['mul'] = {}
                    seasonality['mul']['period'] = period
                    #try:
                    #    result = seasonal_decompose(df['value'], model='mul', period=period)

                    #    seasonality['mul']['error'] = result.resid.subtract(1).abs().max()
                    #except Exception as e:
                    #    print("HO STATO IO: ", ris['name'])

                
                else:
                    stationarity = {}
                    stationarity['stationary'] = True
                    stationarity['p_value'] = 0
                    acf_res = {}
                    seasonality = {}
            
                ris['metadata'] = {'stationarity' : stationarity, 'autocorrelation': acf_res, 'seasonality': seasonality}
                executionTime = time.time() - start
                gMeta.labels(ris['name']).set(executionTime)

                while True:
                    try:
                        # Provo a scrivere su kafka
                        p.produce(topic, value=json.dumps(ris), callback=delivery_callback)
                        p.poll(0)
                        break
                    except BufferError:
                        print('%% Local producer queue is full (%d messages awaiting delivery): try again\n' % len(p), file=sys.stderr)
                        time.sleep(1)
                    except KafkaException as err:
                        print("Error: {}".format(err), file=sys.stderr)
                        if not(err.args[0].retriable()):
                            break # accettiamo di perdere un campione
                        time.sleep(1)


def everyY():
    start_time = parse_datetime("12h")
    end_time = parse_datetime("now")
    
    
    # Ottengo le metriche da prometheus
    for metric_name in metric_name_list:
        try:
            metric_data = prom.get_metric_range_data(
                metric_name=metric_name,
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as err:
            print("Errore di connessione: {}".format(err), file=sys.stderr)
            return

        print("Ho ricevuto i dati")
        # Controllo che il filtro "matchi" effettivamente qualche metrica
        if len(metric_data) == 0:
            # Ricostruisco il filtro come se fosse PromQL
            message = "Non è presente alcuna metrica che corrisponde al filtro: " + metric_name
            if len(label_config) > 0 :
                message = message + "{"
                for elem in label_config:
                    message = message + elem + "='" + label_config[elem] + "', "
                message = message[:-2] + "}"
            print(message)
        else:
            # Chiedo (tramite gRPC in modalità sincrona) all'SLA manager di ritornarmi il set di metriche
            print("Prendo il set")
            sla_set = []
            with grpc.insecure_channel('{}:{}'.format(os.environ['GRPC_SERVER'], os.environ['GRPC_PORT'])) as channel:
                stub = sla_pb2_grpc.SlaServiceStub(channel)
                while True: # at least once. La richiesta è idempotente
                    try:
                        for response in stub.GetSLASet(sla_pb2.SLARequest()):  
                            sla_elem = {}
                            sla_elem['name'] = response.metric
                            sla_elem['seasonality'] = {}
                            sla_elem['seasonality']['add_period'] = response.seasonality.add
                            sla_elem['seasonality']['mul_period'] = response.seasonality.mul
                            sla_set.append(sla_elem) 
                        print("Ho ottenuto il set", sla_set)
                        break
                    except grpc.RpcError as e:
                        print("[gRPC] Errore: ", e)
                        time.sleep(5)
            

            # Per ogni metrica ritornata dal prometheus
            for metric_data_i in metric_data:
                ris = {}
                ris['name'] = metric_data_i['metric']
                ris['values'] = {}
                metric_df12 = MetricRangeDataFrame(metric_data_i)
                metric_df12 = metric_df12.dropna()

                # Calcolo i valori relativi all'ultima ora
                start = time.time()
                metric_df_1 = metric_df12.last("1h")
                min = metric_df_1['value'].min()
                max = metric_df_1['value'].max()
                mean = metric_df_1['value'].mean()
                dev = metric_df_1['value'].std()
                ris['values']['1h'] = {'min': min, 'max': max, 'avg': mean, 'std_dev': dev}
                executionTime = time.time() - start
                g1h.labels(ris['name']).set(executionTime)

                # Calcolo i valori relativi alle ultime 3 ore
                start = time.time()
                metric_df_3 = metric_df12.last("3h")
                min = metric_df_3['value'].min()
                max = metric_df_3['value'].max()
                mean = metric_df_3['value'].mean()
                dev = metric_df_3['value'].std()
                ris['values']['3h'] = {'min': min, 'max': max, 'avg': mean, 'std_dev': dev}
                executionTime = time.time() - start
                g3h.labels(ris['name']).set(executionTime)

                # Calcolo i valori relativi alle ultime 12 ore
                start = time.time()
                min = metric_df12['value'].min()
                max = metric_df12['value'].max()
                mean = metric_df12['value'].mean()
                dev = metric_df12['value'].std()
                ris['values']['12h'] = {'min': min, 'max': max, 'avg': mean, 'std_dev': dev}
                executionTime = time.time() - start
                g12h.labels(ris['name']).set(executionTime)


                # Verifico se la metrica dell'attuale iterazione fa parte dell'sla set  
                for elem in sla_set:
                    if elem['name'] == ris['name']:
                        start = time.time()

                        print("ci sono")

                        # Per la data metrica richiediamo più campioni
                        
                        metric_name_prediction = elem['name']['__name__']
                        #print(metric_name_prediction)
                        del elem['name']['__name__']
                        label_config_prediction = elem['name']
                        # Ottengo le metriche da prometheus
                        try:
                            metric_data_prediction = prom.get_metric_range_data(
                                metric_name=metric_name_prediction,
                                label_config=label_config_prediction,
                                start_time=parse_datetime("15d"), # abbiamo 5 giorni di dati
                                end_time=parse_datetime("now"),
                            )
                        except Exception as err:
                            print("Errore di connessione: {}".format(err), file=sys.stderr)
                            return

                        metric_df_prediction = MetricRangeDataFrame(metric_data_prediction)
                        metric_df_prediction = metric_df_prediction['value'].dropna()
                    
                        

                        metric_df_prediction = metric_df_prediction[metric_df_prediction.index.notnull()]
                        print("Dopo index drop: ", metric_df_prediction)
                        # ricampionamo in funzione del periodo per diminuire i tempi di esecuzione
                        resample = 1
                        if elem['seasonality']['add_period'] > 1440 or elem['seasonality']['mul_period'] > 1440:
                            resample = 5
                        elif elem['seasonality']['add_period'] > 720 or elem['seasonality']['mul_period'] > 720:
                            resample = 2
                    
                        metric_df_prediction = metric_df_prediction.resample(rule=str(resample)+'T').mean()
                        metric_df_prediction = metric_df_prediction.interpolate()
                        # Dividiamo 90/10
                        #data_len = metric_df_prediction.size
                        train = metric_df_prediction.iloc[:int(-10/resample)]#.iloc[:-int(data_len*0.1)]
                        test = metric_df_prediction.iloc[int(-10/resample):]#.iloc[-int(data_len*0.1):]
                        
                        not_calculated = 0
                        # Predico i prossimi 10 minuti (f_s = 1/1 min => 10 campioni, se ricampionato 10/resample)
                        prediction_rmse = {}
                        prediction_add = ""
                        try:
                            # Se non è costante
                            if elem['seasonality']['add_period'] != 0:
                                print("Ho il periodo add: ", elem['seasonality']['add_period'])
                                #if elem['seasonality']['add_period'] > 1440 :
                                #    tsmodel = ExponentialSmoothing(train, trend='add', seasonal='add',seasonal_periods=int(elem['seasonality']['add_period']/resample/10)).fit()
                                #else:
                                tsmodel = ExponentialSmoothing(train, trend='add', seasonal='add',seasonal_periods=int(elem['seasonality']['add_period']/resample)).fit()
                                prediction_add = tsmodel.forecast(20/resample)
                                prediction_rmse['es_add'] = {}
                                #prediction_rmse['es_add']['all_test'] = np.sqrt(mean_squared_error(test, prediction_add))
                                prediction_rmse['es_add']['10m'] = np.sqrt(mean_squared_error(test, prediction_add[:int(10/resample)]))
                            # Se è costante
                            else:
                                # Creiamo una previsione fittizia mantenendo l'ultimo valore
                                last_sample_time = metric_df_prediction.index[-1]
                                next_sample_time = last_sample_time + pd.DateOffset(minutes=1)
                                index = pd.date_range(start=next_sample_time, periods=int(10/resample), freq='T')
                                prediction_add = pd.DataFrame(np.full(int(10/resample), metric_df_prediction.tail(1)),index =index)
                                prediction_rmse['es_add'] = {}
                                prediction_rmse['es_add']['10m'] = 0 #Supponiamo nullo l'errore
                        except Exception as err:
                            print("Errore durante la predizione (add): ", err)
                            not_calculated = not_calculated + 1
                        try:    
                            prediction_mul = ""
                            if elem['seasonality']['mul_period'] != 0:
                                print("Ho il periodo mul: ", elem['seasonality']['mul_period'])
                                #if elem['seasonality']['mul_period'] > 1440 :
                                #    tsmodel = ExponentialSmoothing(train, trend='add', seasonal='mul',seasonal_periods=int(elem['seasonality']['mul_period']/resample/10)).fit()
                                #else:
                                tsmodel = ExponentialSmoothing(train, trend='add', seasonal='mul',seasonal_periods=int(elem['seasonality']['mul_period']/resample)).fit()
                                prediction_mul = tsmodel.forecast(20/resample)
                                prediction_rmse['es_mul'] = {}
                                prediction_rmse['es_mul']['10m'] = np.sqrt(mean_squared_error(test, prediction_mul[:int(10/resample)]))
                            
                            # Se è costante
                            else:
                                # Creiamo una previsione fittizia mantenendo l'ultimo valore
                                last_sample_time = metric_df_prediction.index[-1]
                                next_sample_time = last_sample_time + pd.DateOffset(minutes=1)
                                index = pd.date_range(start=next_sample_time, periods=int(10/resample), freq='T')
                                prediction_mul = pd.DataFrame(np.full(int(10/resample), metric_df_prediction.tail(1)),index =index)
                                prediction_rmse['es_mul'] = {}
                                prediction_rmse['es_mul']['10m'] = 0 #Supponiamo nullo l'errore

                        except Exception as err:
                            print("Errore durante la predizione (mul): ", err)
                            not_calculated = not_calculated + 2


                        # ARIMA Abbiamo lasciato perdere, non riusciamo a farla funzionare
                        """"
                        arima_res = auto_arima(train)
                        model = ARIMA(train, order=arima_res.order).fit()
                        prediction_arima = model.predict(start=len(train), end=len(train)+len(test)-1, dynamic=False, typ='levels')
                        prediction_rmse['arima'] = {}
                        prediction_rmse['arima']['all_test'] = np.sqrt(mean_squared_error(test, prediction_arima))
                        prediction_rmse['arima']['10m'] = np.sqrt(mean_squared_error(test[:10], prediction_arima[:10]))
                        """

                        print("rmse: ", prediction_rmse)
                        print("prediction add: ", prediction_add)
                        print("prediction mul: ", prediction_mul)

                        if not_calculated == 3: #nessuna delle due
                            pass
                        elif not_calculated == 2: #manca mul
                            if prediction_add.size > int(10/resample):
                                prediction = prediction_add.iloc[int(10/resample):]  
                            else:
                                prediction = prediction_add 
                            ris['prediction'] = {}
                            ris['prediction']['min'] = float(prediction.min())
                            ris['prediction']['max'] = float(prediction.min())
                            ris['prediction']['avg'] = float(prediction.min())
                            ris['prediction']['values'] = prediction.to_csv()
                            ris['prediction']['rmse'] = prediction_rmse['es_add']['10m']
                        elif not_calculated == 1: #manca add
                            if prediction_mul.size > int(10/resample):
                                prediction = prediction_mul.iloc[int(10/resample):]  
                            else:
                                prediction = prediction_mul 
                            ris['prediction'] = {}
                            ris['prediction']['min'] = float(prediction.min())
                            ris['prediction']['max'] = float(prediction.min())
                            ris['prediction']['avg'] = float(prediction.min())
                            ris['prediction']['values'] = prediction.to_csv()
                            ris['prediction']['rmse'] = prediction_rmse['es_mul']['10m']
                        else: #ci sono entrambe
                            if prediction_rmse['es_add']['10m'] < prediction_rmse['es_mul']['10m']:
                                if prediction_add.size > int(10/resample):
                                    prediction = prediction_add.iloc[int(10/resample):]  
                                else:
                                    prediction = prediction_add 
                            else:
                                if prediction_mul.size > int(10/resample):        
                                    prediction = prediction_mul.iloc[int(10/resample):]  
                                else:
                                    prediction = prediction_mul
                            prediction_error = prediction_rmse['es_add']['10m'] if prediction_rmse['es_add']['10m'] < prediction_rmse['es_mul']['10m'] else prediction_rmse['es_mul']['10m']
                        
                            ris['prediction'] = {}
                            ris['prediction']['min'] = float(prediction.min())
                            ris['prediction']['max'] = float(prediction.min())
                            ris['prediction']['avg'] = float(prediction.min())
                            ris['prediction']['values'] = prediction.to_csv()
                            ris['prediction']['rmse'] = prediction_error

                            #print("prediction: ", prediction)
                            #print("prediction csv:", prediction.to_csv())
                            #print("ris prima: ", ris)
                            # plt.figure(figsize=(24,10))
                            # plt.ylabel('Values', fontsize=14)
                            # plt.xlabel('Time', fontsize=14)
                            # plt.title('Values over time', fontsize=16)
                            # plt.plot(test,"-",label = 'real')
                            # plt.plot(prediction_add,"-",label = 'predAdd')
                            # plt.plot(prediction_mul,"-",label = 'predMul')
                            # #plt.plot(prediction_arima,"*",label = 'predArima')
                            # plt.legend(title='Series')
                            # plt.savefig("file/{}.png".format(elem['name']['mountpoint'].replace("/", "_")))                        
                            #print("ris dopo: ", ris)

                        executionTime = time.time() - start
                        gPre.labels(ris['name']).set(executionTime)
                while True:
                    try:
                        # Provo a scrivere su kafka
                        p.produce(topic, value=json.dumps(ris), callback=delivery_callback)
                        p.poll(0)
                        break
                    except BufferError:
                        print('%% Local producer queue is full (%d messages awaiting delivery): try again\n' % len(p), file=sys.stderr)
                        time.sleep(1)
                    except KafkaException as err:
                        print("Error: {}".format(err), file=sys.stderr)
                        if not(err.args[0].retriable()):
                            break # accettiamo di perdere un campione
                        time.sleep(1)