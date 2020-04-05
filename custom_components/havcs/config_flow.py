"""Config flow for MQTT."""
from collections import OrderedDict
import queue
import ssl
from hashlib import sha1
import json
import voluptuous as vol
import os
import re
import logging

from homeassistant import config_entries
from homeassistant.const import (CONF_PORT, CONF_PROTOCOL, CONF_HOST)

from .const import  HAVCS_SERVICE_URL, DEVICE_PLATFORM_DICT, CONF_MODE, CONF_DEVICE_CONFIG, CONF_APP_KEY, CONF_APP_SECRET, CONF_BROKER, CONF_ENTITY_KEY, CONF_URL, CONF_PROXY_URL, CONF_SKIP_TEST, CONF_DISCOVERY, DEFAULT_DISCOVERY, INTEGRATION
from . import util as havcs_util
# from .__init__ import HavcsTestView

_LOGGER = logging.getLogger(__name__)
LOGGER_NAME = 'config_flow'

SOURCE_PLATFORM = 'platform'

@config_entries.HANDLERS.register(INTEGRATION)
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._user_entries = [entry for entry in self._async_current_entries() if entry.source == config_entries.SOURCE_USER]
        if self._user_entries:
            # return self.async_abort(reason='single_instance_allowed')
            return await self.async_step_clear()

        return await self.async_step_base()

    async def async_step_clear(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get('comfirm'):
                for entry in self._user_entries:
                    await self.hass.async_create_task(self.hass.config_entries.async_remove(entry.entry_id))
                return self.async_abort(reason='clear_finish')
            else:
                return self.async_abort(reason='clear_cancel')
        else:
            user_input = {}
        fields = OrderedDict()
        fields[vol.Required('comfirm', default = user_input.get('comfirm', False))] = bool
        return self.async_show_form(
            step_id='clear', data_schema=vol.Schema(fields), errors=errors)  

    async def async_step_base(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._mode = user_input.get('mode')
            self._device_config = 'ui' if user_input[CONF_DEVICE_CONFIG] else 'text'
            user_input.pop(CONF_DEVICE_CONFIG)
            self._platform=[key for key in user_input if user_input[key] is True]
            if not self._platform:
                errors['base'] = 'platform_validation'
            elif self._mode == 0:
                errors[CONF_MODE] = 'mode_validation'
            else:
                return await self.async_step_access()
        else:
            user_input = {}
        fields = OrderedDict()
        for platform in DEVICE_PLATFORM_DICT.keys():
            fields[vol.Optional(platform, default = user_input.get(platform, False))] = bool
        fields[vol.Optional(CONF_MODE, default = user_input.get(CONF_MODE, 0))] = vol.In({0: '选择运行模式', 1: '模式1 - http(自建技能)', 2: '模式2 - http+proxy（自建技能）', 3: '模式3 - HAVCS服务（音箱APP技能）'})
        fields[vol.Optional(CONF_DEVICE_CONFIG, default = user_input.get(CONF_DEVICE_CONFIG, True))] = bool
        return self.async_show_form(
            step_id='base', data_schema=vol.Schema(fields), errors=errors)            

    async def async_step_access(self, user_input=None):
        """Confirm the setup."""
        errors = {}

        if user_input is not None:
            if len(user_input[CONF_ENTITY_KEY]) != 0 and len(user_input[CONF_ENTITY_KEY]) != 16:
                errors[CONF_ENTITY_KEY] = 'entity_key_validation'

            if user_input.get(CONF_SKIP_TEST, False) is False:
                if len(user_input.get(CONF_PROXY_URL, '')) != 0:
                    matchObj = re.match(r'' + HAVCS_SERVICE_URL + '/h2m2h/(.+?)/(.*)', user_input[CONF_PROXY_URL], re.M|re.I)
                    if not matchObj:
                        errors[CONF_PROXY_URL] = 'proxy_url_validation'
                # check mqtt
                if not errors:
                    if CONF_BROKER in user_input: 
                        test_results = await self.hass.async_add_executor_job(
                            test_mqtt, user_input.get(CONF_BROKER), user_input.get(CONF_PORT),
                            user_input.get(CONF_APP_KEY), user_input.get(CONF_APP_SECRET), user_input.get(CONF_PROXY_URL))
                        if not test_results[0][0]:
                            errors['base'] = 'connecttion_test_' + str(test_results[0][1])
                        # check proxy url
                        elif CONF_PROXY_URL in user_input and len(test_results) !=2 :
                            errors['base'] = 'proxy_test'
                        _LOGGER.debug("[%s] mqtt test result: %s", LOGGER_NAME, test_results)
                    # check api
                    elif CONF_URL in user_input:
                        test_result = await self.hass.async_add_executor_job(
                            test_http, self.hass, user_input[CONF_URL])
                        if not test_result[0]:
                            _LOGGER.debug("[%s] http test result: %s", LOGGER_NAME, test_result)
                            errors['base'] = 'http_test'

            for entry in [entry for entry in self._async_current_entries() if entry.source == config_entries.SOURCE_IMPORT]:
                _LOGGER.info("[%s] overwrite Intergation generated by configuration.yml with the new one from the web", LOGGER_NAME)
                await self.hass.async_create_task(self.hass.config_entries.async_remove(entry.entry_id))
            if user_input[CONF_SKIP_TEST] or not errors:
                conf = {'platform': self._platform}
                clients = {user_input[platform+'_id']: user_input[platform+'_secret'] for platform in self._platform if platform+'_id' in user_input} 
                mode = []
                if self._mode == 1:
                    conf.update({
                        'http':{'clients':clients},
                        'setting':{},
                        'device_config': self._device_config
                    })
                    mode.append('http')
                elif self._mode == 2:
                    conf.update({
                        'http':{'clients':clients},
                        'http_proxy':{},
                        'setting': {'broker': user_input[CONF_BROKER], 'port': user_input[CONF_PORT], 'app_key': user_input[CONF_APP_KEY], 'app_secret': user_input[CONF_APP_SECRET], 'entity_key': user_input[CONF_ENTITY_KEY]},
                        'device_config': self._device_config
                        })
                    mode.append('http_proxy')
                elif self._mode == 3:
                    conf.update({
                        'skill': {},
                        'setting': {'broker': user_input[CONF_BROKER], 'port': user_input[CONF_PORT], 'app_key': user_input[CONF_APP_KEY], 'app_secret': user_input[CONF_APP_SECRET], 'entity_key': user_input[CONF_ENTITY_KEY]},
                        'device_config': self._device_config
                        })
                    mode.append('skill')
                
                havcs_entries = self.hass.config_entries.async_entries(INTEGRATION)
                # sub entry for every platform
                entry_platforms = set([entry.data.get('platform') for entry in havcs_entries if entry.source == SOURCE_PLATFORM])
                conf_platforms = set(self._platform)
                new_platforms = conf_platforms - entry_platforms
                for platform in new_platforms:
                    self.hass.async_create_task(self.hass.config_entries.flow.async_init(
                        INTEGRATION, context={'source': SOURCE_PLATFORM},
                        data={'platform': platform, 'mode': mode}
                    ))
                remove_platforms = entry_platforms - conf_platforms
                for entry in [entry for entry in havcs_entries if entry.source == SOURCE_PLATFORM]:
                    if entry.data.get('platform') in remove_platforms:
                        self.hass.async_create_task(self.hass.config_entries.async_remove(entry.entry_id))
                    else:
                        entry.title=f"接入平台[{entry.data.get('platform')}-{DEVICE_PLATFORM_DICT[entry.data.get('platform')]['cn_name']}]，接入方式{mode}"
                        self.hass.config_entries.async_update_entry(entry)
                
                return self.async_create_entry(
                    title='主配置[Web界面]', data=conf)
        else:
            user_input = {}
        fields = OrderedDict()

        if self._mode == 1:
            for platform in self._platform:
                fields[vol.Required(platform+'_id', default = user_input.get(platform+'_id', platform))] = str
                fields[vol.Required(platform+'_secret', default = user_input.get(platform+'_secret', ''))] = str
            fields[vol.Optional(CONF_ENTITY_KEY, default = user_input.get(CONF_ENTITY_KEY, ''))] = str
            fields[vol.Required(CONF_SKIP_TEST, default = user_input.get(CONF_SKIP_TEST, False))] = bool
            fields[vol.Optional(CONF_URL, default = user_input.get(CONF_URL, 'https://[你的公网域名或IP:端口号]/havcs/auth/authorize'))] = str
        else:
            fields[vol.Required(CONF_BROKER, default = user_input.get(CONF_BROKER, 'mqtt.ljr.im'))] = str
            fields[vol.Required(CONF_PORT, default = user_input.get(CONF_PORT, 28883))] = vol.Coerce(int)
            fields[vol.Required(CONF_APP_KEY, default = user_input.get(CONF_APP_KEY, ''))] = str
            fields[vol.Required(CONF_APP_SECRET, default = user_input.get(CONF_APP_SECRET, ''))] = str
            fields[vol.Optional(CONF_ENTITY_KEY, default = user_input.get(CONF_ENTITY_KEY, ''))] = str
            fields[vol.Required(CONF_SKIP_TEST, default = user_input.get(CONF_SKIP_TEST, False))] = bool    
            if self._mode == 2:
                fields[vol.Optional(CONF_PROXY_URL, default = user_input.get(CONF_PROXY_URL, HAVCS_SERVICE_URL + '/h2m2h/[你的AppKey]/havcs/auth/authorize'))] = str

        # fields[vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY)] = bool

        return self.async_show_form(
            step_id='access', data_schema=vol.Schema(fields), errors=errors)

    async def async_step_import(self, user_input):
        """Import a config entry.

        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        if [entry for entry in self._async_current_entries() if entry.source in [config_entries.SOURCE_USER, config_entries.SOURCE_IMPORT]]:
            return self.async_abort(reason='single_instance_allowed') 
        return self.async_create_entry(title='主配置[configuration.yml]', data={'platform': user_input['platform']})

    async def async_step_platform(self, user_input):
        return self.async_create_entry(title=f"接入平台[{user_input['platform']}-{DEVICE_PLATFORM_DICT[user_input['platform']]['cn_name']}]，接入模块{user_input['mode']}", data=user_input)

def test_mqtt(broker, port, username, password, proxy_url, protocol='3.1'):
    """Test if we can connect to an MQTT broker."""

    import paho.mqtt.client as mqtt

    if protocol == '3.1':
        proto = mqtt.MQTTv31
    else:
        proto = mqtt.MQTTv311

    client = mqtt.Client(protocol=proto)
    if username and password:
        client.username_pw_set(username, password)

    certificate = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ca.crt')
    client.tls_set(ca_certs = certificate, cert_reqs = ssl.CERT_NONE)

    result = queue.Queue(maxsize=2)

    def on_connect(client_, userdata, flags, result_code):
        """Handle connection result."""
        _LOGGER.debug("[%s] connection check: %s, result code [%s]", LOGGER_NAME, result_code == mqtt.CONNACK_ACCEPTED, result_code)
        result.put((result_code == mqtt.CONNACK_ACCEPTED, result_code))
        if proxy_url:
            client.subscribe('ai-home/http2mqtt2hass/'+username+'/request/#',qos=0)

    def on_subscribe(client, userdata, mid, granted_qos):
        from urllib.request import urlopen
        import urllib.error
        import urllib.parse

        data = urllib.parse.urlencode({'data': 'test'}).encode('utf-8')
        # 会阻塞on_message，不等待回复（mqtt回复）
        response = urlopen(proxy_url, data = data, timeout= 2)
        # try:
        #     data = urllib.parse.urlencode({'data': 'test'}).encode('utf-8')
        #     response = urlopen(proxy_url, data = data, timeout= 2)
        #     print("response 的返回类型：",type(response))
        #     print("反应地址信息: ",response)
        #     print("头部信息1(http header)：\n",response.info())
        #     print("头部信息2(http header)：\n",response.getheaders())
        #     print("输出头部属性信息：",response.getheader("Server"))
        #     print("响应状态信息1(http status)：\n",response.status)
        #     print("响应状态信息2(http status)：\n",response.getcode())
        #     print("响应 url 地址：\n",response.geturl())
        #     page = response.read()
        #     print("输出网页源码:",page.decode('utf-8'))
        # except urllib.error.URLError as e:
        #     print('访问代理转发服务器失败: ', e.reason)
        # except Exception as e:
        #     import traceback
        #     print(type(e))
        #     print('访问代理转发服务器失败: ', traceback.format_exc())
        # else:   
        #     print('访问代理转发服务器正常.')
    def on_message(client, userdata, msg):
        _LOGGER.debug("[%s] proxy check: success receive messge from proxy [%s]", LOGGER_NAME, msg.topic+", "+str(msg.payload))
        try:
            matchObj = re.match(r''+HAVCS_SERVICE_URL+'/h2m2h/(.+?)/(.*)', proxy_url, re.M|re.I)
            if matchObj:
                forward_uri = '/' + matchObj.group(2)
            decrypt_key = bytes().fromhex(sha1(password.encode("utf-8")).hexdigest())[0:16]
            payload = havcs_util.AESCipher(decrypt_key).decrypt(msg.payload)
            req = json.loads(payload)
            req_uri = req.get('uri', '/')
            if forward_uri == req_uri:
                result.put((True, 0))
            _LOGGER.debug("[%s] proxy check: ok, forward uri [%s], receive uri [%s]", LOGGER_NAME, forward_uri, req_uri)
        except:
            import traceback
            _LOGGER.error("[%s] %s", LOGGER_NAME, traceback.format_exc())
        finally:
            client.publish(msg.topic.replace('/request/','/response/'), payload=msg.payload, qos=0, retain=False)

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message

    client.connect_async(broker, port)
    client.loop_start() # 与loop_start（）一起使用以非阻塞方式连接。 直到调用loop_start（）之前，连接才会完成。

    connection_result = None
    proxy_result = None
    try:
        connection_result = result.get(timeout=5)
        proxy_result = result.get(timeout=5)
        return [connection_result, proxy_result]
    except queue.Empty:
        if connection_result:
            return [connection_result]
        else:
            return [(False, 99)]
    finally:
        client.disconnect()
        client.loop_stop()

def test_http(hass, url):
    # hass.http.register_view(HavcsTestView())
    import requests
    try:
        response = requests.head(HAVCS_SERVICE_URL + '/api/forward.php?url=' + url, timeout= 5)
        return (response.status_code == 200, response.status_code)
    except:
        return (False, 0)