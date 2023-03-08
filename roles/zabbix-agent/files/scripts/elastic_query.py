#!/usr/bin/env python
# -*- coding: utf-8 -*-

from elasticsearch import Elasticsearch
import json
import sys

reload(sys)
sys.setdefaultencoding('utf-8')

ES_HOSTS = [{"host": "10.127.96.21", "port": 9200}, {"host": "10.127.96.22", "port": 9200},
            {"host": "10.127.96.23", "port": 9200}]
ES_USER = 'kibana'
ES_PWD = 'welcome001'


class ElasticInvoke:

    def __init__(self):
        self.es = Elasticsearch(ES_HOSTS, http_auth=(ES_USER, ES_PWD), scheme="http", timeout=10)

    def cluster_health(self, path_index, q_param):
        print json.dumps(self.es.cluster.health(index=path_index, params=q_param)).encode('utf-8')

    def cluster_stats(self, path_node_id, q_param):
        print json.dumps(self.es.cluster.stats(node_id=path_node_id, params=q_param)).encode('utf-8')


elastic_invoke = ElasticInvoke()

switch = {
    'cluster_health': elastic_invoke.cluster_health,
    'cluster_stats': elastic_invoke.cluster_stats
}

# https://elasticsearch-py.readthedocs.io/en/6.3.1/connection.html
search_type = sys.argv[1]
path_param = None
query_param = {}

if len(sys.argv) > 2 and str.strip(sys.argv[2]) != "":
    path_param = str.strip(sys.argv[2])

if len(sys.argv) > 3 and str.strip(sys.argv[3]) != "":
    query_param = json.loads(sys.argv[3])

switch.get(search_type)(path_param, query_param)
