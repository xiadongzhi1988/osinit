#!/usr/bin/env python
# -*- coding: utf-8 -*-

from elasticsearch import Elasticsearch
import json
import sys
import os
import urllib2

reload(sys)
sys.setdefaultencoding('utf-8')

"""
获取最近一段时间内有特定告警的日志，将日志内容通过zabbix trapper定位到具体的host插入
arg1: zabbix host ip
arg2: zabbix syslog trapper item key name
arg3: elastic search match index 
arg4: elastic search range minites
arg5: elastic syslog match keyword
"""

zabbix_user = "monitor_admin"
zabbix_pwd = "welcome001"
arg_zbx_ip = sys.argv[1]
arg_zbx_trapper_key = sys.argv[2]
arg_el_index = sys.argv[3]
arg_el_range_min = sys.argv[4]
arg_el_syslog_keyword = sys.argv[5]
ES_HOSTS = [{"host": "10.127.96.21", "port": 9200}, {"host": "10.127.96.22", "port": 9200},{"host": "10.127.96.23", "port": 9200}]


# zabbix_user = "admin"
# zabbix_pwd = "zabbix"
# arg_zbx_ip = "10.135.8.130"
# arg_zbx_trapper_key = "syslog_trapper"
# arg_el_index = "fluentd.system.*"
# arg_el_range_min = "10"
# arg_el_syslog_keyword = "[Error|Error \"tls"
# ES_HOSTS = [{"host": "10.138.106.243", "port": 9200}]

ES_USER = 'elastic'
ES_PWD = 'welcome001'


class ElasticInvoke:

    def __init__(self):
        self.es = Elasticsearch(ES_HOSTS, http_auth=(ES_USER, ES_PWD), scheme="http", timeout=5)

    # 得到最近一段时间匹配关键字的host以及消息内容
    def query_log_by_host(self, index_name, interval_min, msg_keyword_list):
        match_phrase_list = []
        for msg_keyword in msg_keyword_list:
            match_phrase_list.append({"match_phrase": {
                "message": msg_keyword
            }})

        querydic = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "should": match_phrase_list
                            }
                        }
                    ],
                    "filter": [
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": "now-{}m/m".format(interval_min)
                                }
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "Hostlist": {
                    "terms": {
                        "field": "host.keyword",
                        "size": 100000
                    },
                    "aggs": {
                        "iplist": {
                            "terms": {
                                "field": "iplist.keyword"
                            }
                        },
                        "msg": {
                            "terms": {
                                "field": "message.keyword"
                            }
                        }
                    }
                }
            }
        }

        return self.es.search(index=index_name, body=querydic, size=0,
                              filter_path=["aggregations.Hostlist.buckets"])


elastic_invoke = ElasticInvoke()
search_res = elastic_invoke.query_log_by_host(arg_el_index, arg_el_range_min, arg_el_syslog_keyword.split("==="))

# 整理返回的字典
elastic_array = []
for h in search_res["aggregations"]["Hostlist"]["buckets"]:
    ip_array = []
    msg_content = ""
    # 组装ip
    for i in h["iplist"]["buckets"]:
        ip_array.append(i["key"])
    # 组装消息
    for m in h["msg"]["buckets"]:
        msg_content = msg_content + "Count:{0}, Msg:{1} \r".format(m["doc_count"], m["key"])

    elastic_array.append({"host": h["key"], "ip_array": ip_array, "msg": msg_content})


# 调用zabbix sender发送数据给zabbix trapper
def call_zabbix_trapper(tagget_host, msg):
    msg = msg.replace("\"", "\\\"")
    ret = os.popen(
        "zabbix_sender -z {0} -p 10051 -s \"{1}\" -k \"{2}\" -o \"{3}\"".format(arg_zbx_ip,
                                                                                tagget_host,
                                                                                arg_zbx_trapper_key,
                                                                                msg))


'''
根据zabbix接口找到对应的host信息，
'''


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


def get_zbx_item_with_host(zbx_call, ip_list, item_key):
    interface_param = {
        "output": ["hostid", "interfaceid", "ip"],
        "filter": {
            "ip": ip_list
        }
    }

    interface_resp = zbx_call.get_request_obj("hostinterface.get", interface_param)
    host_ids = []
    for t in interface_resp["result"]:
        host_ids.append(t["hostid"])

    item_param = {
        "output": ["itemid"],
        "hostids": host_ids,
        "filter": {
            "key_": item_key
        },
        "selectHosts": "extend"
    }
    item_resp = zbx_call.get_request_obj("item.get", item_param)
    if len(item_resp["result"]) > 0:
        return item_resp["result"][0]
    else:
        return None


zabbix_call = ZabbixInvoke("http://{0}/zabbix/api_jsonrpc.php".format(arg_zbx_ip), zabbix_user,
                           zabbix_pwd)

for elastic_obj in elastic_array:
    item_host = get_zbx_item_with_host(zabbix_call, elastic_obj["ip_array"], arg_zbx_trapper_key)
    if item_host is not None:
        print item_host["hosts"][0]["name"]
        call_zabbix_trapper(item_host["hosts"][0]["host"], elastic_obj["msg"])
