#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib2
import json
import sys

reload(sys)
sys.setdefaultencoding('utf-8')


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

    def get_item_obj(self, param_dict):
        req_data = {
            "jsonrpc": "2.0",
            "method": "item.get",
            "params": param_dict,
            "auth": self.__token,
            "id": 1
        }
        return self.__zabbix_request(req_data)


addr_ip = sys.argv[1]
search_key = sys.argv[2]
zabbix_user = "monitor_admin"
zabbix_pwd = "welcome001"
# addr_ip = "10.135.8.130"
# search_key = "zabbix[queue]"
# zabbix_user=""
# zabbix_pwd=""
zabbix_call = ZabbixInvoke("http://{0}/zabbix/api_jsonrpc.php".format(addr_ip), zabbix_user,
                           zabbix_pwd)

item_param = {
    "output": "extend",
    "search": {
        "key_": search_key,
        "limit": 1
    },
    "output": ["itemid", "lastvalue"],
}
item_resp = zabbix_call.get_item_obj(item_param)
itemid = item_resp["result"][0]["itemid"]
if len(item_resp["result"]) == 0:
    print ""
else:
    print item_resp["result"][0]["lastvalue"]
