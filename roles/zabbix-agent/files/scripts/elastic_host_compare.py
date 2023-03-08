#!/usr/bin/env python
# -*- coding: utf-8 -*-


import urllib2
from elasticsearch import Elasticsearch
import json
import sys

reload(sys)
sys.setdefaultencoding('utf-8')

"""
比较elasticsearch和zabbix的host情况，返回efk未监控的节点信息
arg1: zabbix IP
arg2: zabbix template names ,split by ,
arg3: elastic 使用的索引
arg4: 查询时间范围，分钟
"""

arg_zbx_ip = sys.argv[1]
arg_zbx_templates = str.strip(sys.argv[2]).split(",")
arg_el_index = sys.argv[3]
arg_el_range_min = sys.argv[4]
zabbix_user = "monitor_admin"
zabbix_pwd = "welcome001"
ES_HOSTS = [{"host": "10.127.96.21", "port": 9200}, {"host": "10.127.96.22", "port": 9200},{"host": "10.127.96.23", "port": 9200}]
ES_USER = 'elastic'
ES_PWD = 'welcome001'

# arg_zbx_ip = "10.135.8.130"
# arg_zbx_templates = ["Template OS Linux"]
# arg_el_index = "fluentd.system.*"
# arg_el_range_min = "10"
# zabbix_user = "admin"
# zabbix_pwd = "zabbix"
# ES_HOSTS = [{"host": "10.138.106.243", "port": 9200}]
# ES_USER = 'elastic'
# ES_PWD = 'welcome001'


class ZabbixInvoke:

    def __init__(self, api_url, username, pwd, heads={"Content-Type": "application/json-rpc"}):
        self.__api_url = api_url
        self.__username = username
        self.__pwd = pwd
        self.__headers = heads
        self.__token = self.__login()

    def __login(self):
        login_data = {
            "jsonrpc": "2.0",
            "method": "user.login",
            "params": {
                'user': "" + self.__username + "",
                'password': "" + self.__pwd + "",
            },
            "auth": None,
            "id": 0,
        }
        request = urllib2.Request(self.__api_url, data=json.dumps(login_data),
                                  headers=self.__headers)
        response = urllib2.urlopen(request).read().decode('utf-8')
        response = json.loads(response)
        return response['result']

    # 具体的服务请求方法
    def __zabbix_request(self, req_data):
        request = urllib2.Request(self.__api_url, data=json.dumps(req_data),
                                  headers=self.__headers)
        return json.loads(urllib2.urlopen(request).read().decode('utf-8'))

    def get_request_obj(self, method, param_dict):
        req_data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": param_dict,
            "auth": self.__token,
            "id": 1
        }
        return self.__zabbix_request(req_data)


def get_zabbix_hosts(zbx_call, temp_names):
    temp_param = {
        "output": ["templateid"],
        "filter": {
            "host": temp_names
        }
    }

    temp_resp = zbx_call.get_request_obj("template.get", temp_param)
    temp_ids = []
    for t in temp_resp["result"]:
        temp_ids.append(t["templateid"])

    host_param = {
        "output": ["hostid", "name"],
        "selectInterfaces": ["ip"],
        "templated_hosts": "false",
        "templateids": temp_ids

    }
    host_resp = zbx_call.get_request_obj("host.get", host_param)
    host_dict = {}
    for h in host_resp["result"]:
        host_dict[h["interfaces"][0]["ip"]] = h["name"]
    return host_dict




zabbix_call = ZabbixInvoke("http://{0}/zabbix/api_jsonrpc.php".format(arg_zbx_ip), zabbix_user,
                           zabbix_pwd)

# 得到zabbix已有的host信息
zbx_host_dict = get_zabbix_hosts(zabbix_call, arg_zbx_templates)


class ElasticInvoke:

    def __init__(self):
        self.es = Elasticsearch(ES_HOSTS, http_auth=(ES_USER, ES_PWD), scheme="http", timeout=40)

    def search_hosts(self,index_name, interval_min,):
        querydic = {
            "query": {
                "range": {
                    "@timestamp": {
                        "gte": "now-{}m/m".format(interval_min)
                    }
                }
            },
            "aggs": {
                "iplist": {
                    "terms": {
                        "field": "iplist.keyword",
                        "size": 100000
                    }
                }
            }
        }

        return self.es.search(index=index_name, body=querydic, size=0,
                              filter_path=["aggregations.iplist.buckets.key"])


elastic_invoke = ElasticInvoke()
elastic_aggr_hosts = elastic_invoke.search_hosts(arg_el_index,arg_el_range_min)


# 整理返回的字典
elastic_iplist=elastic_aggr_hosts["aggregations"]["iplist"]["buckets"]
for ipk in elastic_iplist:
    if zbx_host_dict.has_key(ipk["key"]):
        del zbx_host_dict[ipk["key"]]

print json.dumps(zbx_host_dict,indent=1).encode('utf-8')

