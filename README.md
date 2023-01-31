<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->

<!-- code_chunk_output -->

- [Abstract](#-abstract-)
- [Istruzioni](#-istruzioni-)
  - [Docker compose](#-docker-compose-)
  - [Kubernetes](#-kubernetes-)
    - [Build delle immagini](#-build-delle-immagini-)
    - [Deployment](#-deployment-)
  - [Caricamento SLA set](#-caricamento-sla-set-)
    - [Postman](#-postman-)
    - [Curl](#-curl-)

<!-- /code_chunk_output -->
# Abstract

Si vuole realizzare un sistema distribuito per il monitoraggio di
un’applicazione. L’applicazione espone già le metriche da monitorare
tramite un server Prometheus. Vengono realizzati i seguenti
microservizi:

-   ETL data pipeline: esegue due loop in parallelo:

    -   il primo con periodo di **2** min che si occupa di calcolare i
        valori statistici di aggregazione e di effettuare la predizione
        dei successivi 10 minuti per le metriche dell’SLA set.

    -   il secondo con periodo di **1h** che si occupa di calcolare i
        metadati per ogni metrica esposta dal Prometheus

    Entrambi i loop inoltrano i dati al topic kafka "prometheusdata".
    Vengono monitorati i tempi di esecuzione delle varie funzionalità
    mediante un exporter Prometheus.

-   Data Storage: consumer kafka del topic "prometheusdata" che si
    occupa di scrivere i dati ricevuti dall’ETL data pipeline e di
    memorizzarli in un database MongoDB

-   Data Retreival: interfaccia REST che permette di estrarre le
    informazioni contenute nel database.

-   SLA Manager: microservizio che consente, tramite interfaccia REST la
    definizione dell’SLA set e la possibilità di sapere lo stato
    dell’SLA. Tramite interfaccia gRPC consente all’ETL data pipeline di
    ottenere l’SLA set. In fase di definizione dell’SLA set è possibile
    indicare 5 metriche e, per ognuna di esse, il range all’interno del
    quale il valore della metrica deve rimanere e il tempo necessario
    per far scattare l’allarme per la violazione.

Per il deploy del sistema si è utilizzato un **Docker Compose**. È stata
effettuata anche una prova di deployment tramite l’orchestratore di
container **Kubernetes**. Le metriche scelte sono:

-   node_filesystem_avail_bytes

-   cpuTemp

-   diskUsage

-   realUsedMem

-   networkTroughput


# Istruzioni

Prerequisiti:

-   Docker

-   Postman (opzionale)

I comandi descritti a seguire vanno lanciati dalla directory principale
del progetto.

## Docker compose

Per procedere con l’esecuzione del sistema è sufficiente eseguire il
comando:

``` bash
  $ docker compose up
```

Durante la prima esecuzione del comando verrà eseguito il pull delle
immagini pubbliche preesistenti e il build delle immagini create ad hoc.

## Kubernetes

### Build delle immagini

Se è stato già eseguito il docker compose saltare questo passaggio.
Altrimenti per eseguire il build delle immagini:

``` bash
  $ docker compose build
```

dal momento che le immagini utilizzate sono le stesse.

### Deployment

Per il depolyment, utilizzando un qualsiasi cluster Kubernetes (anche
composto da un solo nodo come ad esempio minikube, kind o Docker
Desktop), applicare tutti i file di configurazione yaml contenuti nella
cartella Kubernetes. Dalla directory del progetto:

``` bash
  $ kubectl apply -f Kubernetes -R
```

## Caricamento SLA set

Ulteriore passo per provare le API REST e quello di definire l’SLA set
seguendo una delle due procedure illustrate a seguire.

### Postman

Andare su `File` \> `Import...`

Nella finestra che si apre andare nel tab `File` \> `Choose Files` e
selezionare il file `DSBD.postman_collection.json`. Accettarsi che le
spunte siano selezionate e cliccare su `Import`.

Si avranno a disposizione tutte le API rese disponibili dai
microservizi. Selezionare `SLA Manager > CREATE/UPDATE dell’SLA`

### Curl

Per eseguire manualmente la creazione dell’SLA set eseguire il comando
curl:

``` bash
curl --location --request PUT 'http://localhost:5001/slaset' --header "Content-Type: application/json" -d @sla_set.json 
```
