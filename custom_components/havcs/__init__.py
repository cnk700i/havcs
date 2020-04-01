"""
author: cnk700i
blog: ljr.im
tested simplely On HA version: 0.104.2
"""

import homeassistant.util as hass_util
from homeassistant import config as conf_util
from . import util as havcs_util
from .helper import BindManager
from typing import cast
import jwt
from datetime import datetime, timedelta
import importlib
from base64 import b64decode
from base64 import b64encode
from Crypto.Cipher import AES
import binascii
from hashlib import sha1
import logging
import voluptuous as vol
import os
import ssl
import json
from json.decoder import JSONDecodeError
import requests.certs
from homeassistant import config_entries
from homeassistant.core import Event, ServiceCall, Context, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.components import mqtt
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.const import (CONF_PORT, CONF_PROTOCOL, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED, ATTR_ENTITY_ID)
from homeassistant.exceptions import HomeAssistantError
from . import config_flow
from voluptuous.humanize import humanize_error
import traceback
from homeassistant.components.http import HomeAssistantView
import asyncio
import async_timeout
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import re
from aiohttp import web
from homeassistant.helpers.entity_component import EntityComponent
from urllib import parse
from .const import DEVICE_ATTRIBUTE_DICT, DATA_HAVCS_HANDLER, DATA_HAVCS_CONFIG, DATA_HAVCS_MQTT, DATA_HAVCS_BIND_MANAGER, DATA_HAVCS_ITEMS, DEVICE_PLATFORM_DICT, HAVCS_SERVICE_URL, ATTR_DEVICE_VISABLE, ATTR_DEVICE_ENTITY_ID, ATTR_DEVICE_TYPE, ATTR_DEVICE_NAME, ATTR_DEVICE_ZONE, ATTR_DEVICE_ICON, ATTR_DEVICE_ATTRIBUTES, ATTR_DEVICE_ACTIONS, DEVICE_TYPE_DICT, DEVICE_ATTRIBUTE_DICT, DEVICE_ACTION_DICT, DEVICE_PLATFORM_DICT
from .device import VoiceControllDevice
from voluptuous.error import Error as VoluptuousError
from homeassistant.util.yaml import save_yaml
import shutil
_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)

DOMAIN = 'havcs'
EXPIRATION = None
MODE = []
SOURCE_PLATFORM = 'platform'

CONF_APP_KEY = 'app_key'
CONF_APP_SECRET = 'app_secret'
CONF_CLIENT_ID = 'client_id'
CONF_KEEPALIVE = 'keepalive'
CONF_TOPIC = 'topic'
CONF_BROKER = 'broker'
CONF_CERTIFICATE = 'certificate'
CONF_CLIENT_KEY = 'client_key'
CONF_CLIENT_CERT = 'client_cert'
CONF_TLS_INSECURE = 'tls_insecure'
CONF_TLS_VERSION = 'tls_version'
CONF_ALLOWED_URI = 'allowed_uri'
CONF_ENTITY_KEY = 'entity_key'
CONF_USER_ID = 'user_id'
CONF_HA_URL = 'ha_url'
CONF_SYNC_DEVICE = 'sync_device'
CONF_BIND_DEVICE = 'bind_device'

CONF_PLATFORM = 'platform'
CONF_HTTP = 'http'
CONF_HTTP_PROXY = 'http_proxy'
CONF_SKILL = 'skill'
CONF_SETTING = 'setting'
CONF_DEVICE_CONFIG = 'device_config'
CONF_EXPIRE_IN_HOURS = 'expire_in_hours'

CONF_BIRTH_MESSAGE = 'birth_message'
CONF_WILL_MESSAGE = 'will_message'

PROTOCOL_31 = '3.1'
PROTOCOL_311 = '3.1.1'

DEFAULT_BROKER = 'mqtt.ljr.im'
DEFAULT_PORT = 28883
DEFAULT_KEEPALIVE = 60
DEFAULT_QOS = 0
DEFAULT_PROTOCOL = PROTOCOL_311
DEFAULT_TLS_PROTOCOL = 'auto'
DEFAULT_EXPIRE_IN_HOURS = 24
DEFAULT_ALLOWED_URI = ['/havcs_auth', '/havcs_service']

CLIENT_KEY_AUTH_MSG = 'client_key and client_cert must both be present in the MQTT broker configuration'

SERVICE_RELOAD = 'reload'
SERVICE_DEBUG_DISCOVERY = 'debug_discovery'

SETTING_SCHEMA = vol.Schema({
    vol.Optional(CONF_ENTITY_KEY):vol.All(cv.string, vol.Any(vol.Length(min=16, max=16), '')),
    vol.Optional(CONF_APP_KEY): cv.string,
    vol.Optional(CONF_APP_SECRET): cv.string,
    vol.Optional(CONF_USER_ID): cv.string,
    vol.Optional(CONF_CERTIFICATE): vol.Any('auto', cv.isfile),
    vol.Optional(CONF_CLIENT_ID): cv.string,
    vol.Optional(CONF_KEEPALIVE, default=DEFAULT_KEEPALIVE): vol.All(vol.Coerce(int), vol.Range(min=15)),
    vol.Optional(CONF_BROKER, default=DEFAULT_BROKER): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Inclusive(CONF_CLIENT_KEY, 'client_key_auth', msg=CLIENT_KEY_AUTH_MSG): cv.isfile,
    vol.Inclusive(CONF_CLIENT_CERT, 'client_key_auth', msg=CLIENT_KEY_AUTH_MSG): cv.isfile,
    vol.Optional(CONF_TLS_INSECURE, default=True): cv.boolean,
    vol.Optional(CONF_TLS_VERSION, default=DEFAULT_TLS_PROTOCOL): vol.Any('auto', '1.0', '1.1', '1.2'),
    vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.All(cv.string, vol.In([PROTOCOL_31, PROTOCOL_311])),
    vol.Optional(CONF_TOPIC): cv.string,
})

HTTP_SCHEMA = vol.Schema({
    vol.Optional(CONF_HA_URL): cv.string,
    vol.Optional(CONF_EXPIRE_IN_HOURS, default=DEFAULT_EXPIRE_IN_HOURS): cv.positive_int
})

HTTP_PROXY = vol.Schema({
    vol.Optional(CONF_HA_URL): cv.string,
    vol.Optional(CONF_ALLOWED_URI, default=DEFAULT_ALLOWED_URI): vol.All(cv.ensure_list, vol.Length(min=0), [cv.string])
})

SKILL_SCHEMA = vol.Schema({
    vol.Optional(CONF_SYNC_DEVICE, default=False): cv.boolean,
    vol.Optional(CONF_BIND_DEVICE, default=True): cv.boolean
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PLATFORM): vol.All(cv.ensure_list, vol.Length(min=1), list(DEVICE_PLATFORM_DICT.keys())),
        vol.Optional(CONF_HTTP): vol.Any(HTTP_SCHEMA, None),
        vol.Optional(CONF_HTTP_PROXY): vol.Any(HTTP_PROXY, None),
        vol.Optional(CONF_SKILL): vol.Any(SKILL_SCHEMA, None),
        vol.Optional(CONF_SETTING): vol.Any(SETTING_SCHEMA, None),
        vol.Optional(CONF_DEVICE_CONFIG, default='text'): vol.Any('text', 'ui'),
    })
}, extra=vol.ALLOW_EXTRA)

HAVCS_SERVICE_SCHEMA = vol.Schema({
})

DEVICD_ACTIONS_SCHEMA = vol.Schema({
    vol.In(list(DEVICE_ACTION_DICT.keys())): vol.All(cv.ensure_list, vol.Schema([vol.All(cv.ensure_list, vol.Length(min=3, max=3))]))
})

DEVICE_ENTRY_SCHEMA = vol.Schema({
    vol.Optional(ATTR_DEVICE_VISABLE): vol.All(cv.ensure_list, list(DEVICE_PLATFORM_DICT.keys())),
    vol.Required(ATTR_DEVICE_ENTITY_ID): cv.ensure_list,
    vol.Optional(ATTR_DEVICE_TYPE): vol.In(list(DEVICE_TYPE_DICT.keys())),
    vol.Optional(ATTR_DEVICE_NAME): cv.string,
    vol.Optional(ATTR_DEVICE_ZONE): cv.string,
    vol.Optional(ATTR_DEVICE_ICON): cv.string,
    vol.Optional(ATTR_DEVICE_ATTRIBUTES): vol.All(cv.ensure_list, list(DEVICE_ATTRIBUTE_DICT.keys())),
    vol.Optional(ATTR_DEVICE_ACTIONS): vol.Any(DEVICD_ACTIONS_SCHEMA, vol.All(cv.ensure_list, list(DEVICE_ACTION_DICT.keys())))
},extra=vol.PREVENT_EXTRA)

DEVICE_CONFIG_SCHEMA = vol.Schema({
    cv.entity_id: DEVICE_ENTRY_SCHEMA
})

async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:

    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)  # type: ConfigType
 
    if conf is None:
        # If we have a config entry, setup is done by that config entry.
        # If there is no config entry, this should fail.
        return bool(hass.config_entries.async_entries(DOMAIN))     

    hass.data[DOMAIN][DATA_HAVCS_CONFIG] = conf

    # mode = []
    # if CONF_HTTP in conf:
    #     mode.append(1)
    #     if CONF_HTTP_PROXY in conf:
    #         mode.append(2)
    # if CONF_SKILL in conf:
    #     mode.append(3)

    # havcs_entries = hass.config_entries.async_entries(DOMAIN)
    # # sub entry for every platform
    # entry_platforms = set([entry.data.get('platform') for entry in havcs_entries if entry.source == SOURCE_PLATFORM])
    # conf_platforms = set(conf.get(CONF_PLATFORM))
    # new_platforms = conf_platforms - entry_platforms
    # for platform in new_platforms:
    #     hass.async_create_task(hass.config_entries.flow.async_init(
    #         DOMAIN, context={'source': SOURCE_PLATFORM},
    #         data={'platform': platform, 'mode': mode}
    #     ))
    # remove_platforms = entry_platforms - conf_platforms
    # for entry in [entry for entry in havcs_entries if entry.source == SOURCE_PLATFORM]:
    #     if entry.data.get('platform') in remove_platforms:
    #         hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
    #     else:
    #         entry.title=f"接入平台[{entry.data.get('platform')}-{DEVICE_PLATFORM_DICT[entry.data.get('platform')]['cn_name']}]，接入方式{mode}"
    #         hass.config_entries.async_update_entry(entry)
    # main entry
    if not [entry for entry in hass.config_entries.async_entries(DOMAIN) if entry.source == config_entries.SOURCE_IMPORT]:
        hass.async_create_task(hass.config_entries.flow.async_init(
                DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
                data={'platform': conf.get(CONF_PLATFORM)}
            ))
    return True

async def async_setup_entry(hass, config_entry):
    """Load a config entry."""
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_HAVCS_HANDLER, {})
    hass.data[DOMAIN].setdefault(DATA_HAVCS_CONFIG, {})
    hass.data[DOMAIN].setdefault(DATA_HAVCS_ITEMS, {})
    conf = hass.data[DOMAIN].get(DATA_HAVCS_CONFIG)

    # Config entry was created because user had configuration.yaml entry
    # They removed that, so remove entry.
    if config_entry.source == config_entries.SOURCE_IMPORT:
        if conf is None:
            hass.async_create_task(
                hass.config_entries.async_remove(config_entry.entry_id))
            return False

    elif config_entry.source == SOURCE_PLATFORM:
        if conf is None:
            if [entry for entry in hass.config_entries.async_entries(DOMAIN) if entry.source == config_entries.SOURCE_USER]:
                return True
            else:
                hass.async_create_task(
                    hass.config_entries.async_remove(config_entry.entry_id))
                return False
        else:
                return True

    # If user didn't have configuration.yaml config, generate defaults
    elif config_entry.source == config_entries.SOURCE_USER:
        if not conf:
            conf = CONFIG_SCHEMA({
                DOMAIN: config_entry.data,
            })[DOMAIN]
        elif any(key in conf for key in config_entry.data):
            _LOGGER.warning(
                "[init] Data in your config entry is going to override your "
                "configuration.yaml: %s", config_entry.data)
    
        # conf.update(config_entry.data)

        for key in config_entry.data:
            if key in conf:
                if isinstance(conf[key], dict):
                    conf[key].update(config_entry.data[key])
                else:
                    conf[key] = config_entry.data[key]
            else:
                conf[key] = config_entry.data[key]
        if CONF_HTTP not in config_entry.data and CONF_HTTP in conf:
            conf.pop(CONF_HTTP)
        if CONF_HTTP_PROXY not in config_entry.data and CONF_HTTP_PROXY in conf:
            conf.pop(CONF_HTTP_PROXY)
        if CONF_SKILL not in config_entry.data and CONF_SKILL in conf:
            conf.pop(CONF_SKILL)

    if CONF_HTTP in conf:
        if conf.get(CONF_HTTP) is None:
            conf[CONF_HTTP] = HTTP_SCHEMA({})
        hass.http.register_view(HavcsGateView(hass))
        hass.http.register_view(HavcsAuthView(hass, conf.get(CONF_HTTP, {}).get(CONF_HA_URL, hass.config.api.base_url)))
        global EXPIRATION
        EXPIRATION = timedelta(hours=conf.get(CONF_HTTP).get(CONF_EXPIRE_IN_HOURS, DEFAULT_EXPIRE_IN_HOURS))
        _LOGGER.info('[init] havcs enable "http mode"')
        MODE.append('http')
    if CONF_HTTP_PROXY in conf:
        if conf.get(CONF_HTTP_PROXY) is None:
            conf[CONF_HTTP_PROXY] = HTTP_PROXY({})
        _LOGGER.info('[init] havcs enable "http_proxy mode"')
        if CONF_SETTING not in conf:
            _LOGGER.error('[init] fail to start havcs: http_proxy mode require mqtt congfiguration')
            return False
        MODE.append('http_proxy')
    if CONF_SKILL in conf:
        if conf.get(CONF_SKILL) is None:
            conf[CONF_SKILL] = SKILL_SCHEMA({})
        _LOGGER.info('[init] havcs enable "skill mode"')
        if CONF_SETTING not in conf:
            _LOGGER.error('[init] fail to start havcs: skill mode require mqtt congfiguration')
            return False
        MODE.append('skill')
    
    havcs_util.ENTITY_KEY = conf.get(CONF_SETTING, {}).get(CONF_ENTITY_KEY)
    havcs_util.CONTEXT_HAVCS = Context(conf.get(CONF_SETTING, {}).get(CONF_USER_ID))

    platforms = conf.get(CONF_PLATFORM)
    if platforms:
        manager = hass.data[DOMAIN][DATA_HAVCS_BIND_MANAGER] = BindManager(hass, platforms)
        await manager.async_load()

    device_config = conf.get(CONF_DEVICE_CONFIG)
    if device_config == 'text':
        havcd_config_path = os.path.join(hass.config.config_dir, 'havcs.yaml')
        if not os.path.isfile(havcd_config_path):
            with open(havcd_config_path, "wt") as havcd_config_file:
                havcd_config_file.write('')
        hass.components.frontend.async_remove_panel(DOMAIN)
    else:
        havcd_config_path = os.path.join(hass.config.config_dir, 'havcs-ui.yaml')
        if not os.path.isfile(havcd_config_path):
            if os.path.isfile(os.path.join(hass.config.config_dir, 'havcs.yaml')):
                shutil.copyfile(os.path.join(hass.config.config_dir, 'havcs.yaml'), havcd_config_path)
            else:
                with open(havcd_config_path, "wt") as havcd_config_file:
                    havcd_config_file.write('')
        hass.http.register_view(HavcsDeviceView(hass))
    hass.data[DOMAIN][CONF_DEVICE_CONFIG] = havcd_config_path


    sync_device = conf.get(CONF_SKILL, {}).get(CONF_SYNC_DEVICE)
    bind_device = conf.get(CONF_SKILL, {}).get(CONF_BIND_DEVICE)

    if CONF_HTTP_PROXY not in conf and CONF_SKILL not in conf:
        _LOGGER.debug('[init] havcs only run in http mode, skip mqtt initialization')
    else:
        setting_conf = conf.get(CONF_SETTING)
        app_key = setting_conf.get(CONF_APP_KEY)
        app_secret = setting_conf.get(CONF_APP_SECRET)
        decrypt_key =bytes().fromhex(sha1(app_secret.encode("utf-8")).hexdigest())[0:16]

        allowed_uri = conf.get(CONF_HTTP_PROXY, {}).get(CONF_ALLOWED_URI)
        ha_url = conf.get(CONF_HTTP_PROXY, {}).get(CONF_HA_URL, hass.config.api.base_url)

        broker = setting_conf[CONF_BROKER]
        port = setting_conf[CONF_PORT]
        client_id = setting_conf.get(CONF_CLIENT_ID)
        keepalive = setting_conf[CONF_KEEPALIVE]
        certificate = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ca.crt')
        if os.path.exists(certificate):
            _LOGGER.debug('[init] sucess to autoload ca.crt from %s', certificate)
        else:
            certificate = setting_conf.get(CONF_CERTIFICATE)
        client_key = setting_conf.get(CONF_CLIENT_KEY)
        client_cert = setting_conf.get(CONF_CLIENT_CERT)
        tls_insecure = setting_conf.get(CONF_TLS_INSECURE)
        protocol = setting_conf[CONF_PROTOCOL]

        # For cloudmqtt.com, secured connection, auto fill in certificate
        if (certificate is None and 19999 < conf[CONF_PORT] < 30000 and
                broker.endswith('.cloudmqtt.com')):
            certificate = os.path.join(
                os.path.dirname(__file__), 'addtrustexternalcaroot.crt')

        # When the certificate is set to auto, use bundled certs from requests
        elif certificate == 'auto':
            certificate = requests.certs.where()

        if CONF_WILL_MESSAGE in setting_conf:
            will_message = mqtt.Message(**conf[CONF_WILL_MESSAGE])
        else:
            will_message = None

        if CONF_BIRTH_MESSAGE in setting_conf:
            birth_message = mqtt.Message(**conf[CONF_BIRTH_MESSAGE])
        else:
            birth_message = None

        # Be able to override versions other than TLSv1.0 under Python3.6
        conf_tls_version = setting_conf.get(CONF_TLS_VERSION)  # type: str
        if conf_tls_version == '1.2':
            tls_version = ssl.PROTOCOL_TLSv1_2
        elif conf_tls_version == '1.1':
            tls_version = ssl.PROTOCOL_TLSv1_1
        elif conf_tls_version == '1.0':
            tls_version = ssl.PROTOCOL_TLSv1
        else:
            import sys
            # Python3.6 supports automatic negotiation of highest TLS version
            if sys.hexversion >= 0x03060000:
                tls_version = ssl.PROTOCOL_TLS  # pylint: disable=no-member
            else:
                tls_version = ssl.PROTOCOL_TLSv1

        hass.data[DOMAIN][DATA_HAVCS_MQTT] = mqtt.MQTT(
            hass,
            broker=broker,
            port=port,
            client_id=client_id,
            keepalive=keepalive,
            username=app_key,
            password=app_secret,
            certificate=certificate,
            client_key=client_key,
            client_cert=client_cert,
            tls_insecure=tls_insecure,
            protocol=protocol,
            will_message=will_message,
            birth_message=birth_message,
            tls_version=tls_version,
        )

        success = await hass.data[DOMAIN][DATA_HAVCS_MQTT].async_connect()  # type: bool

        if success is True or success == 'connection_success':
            pass
        else:
            import hashlib
            md5_l = hashlib.md5()
            with open(certificate,mode="rb") as f:
                by = f.read()
            md5_l.update(by)
            local_ca_md5 = md5_l.hexdigest()
            _LOGGER.debug('[init] local ca.crt md5 %s', local_ca_md5)
            from urllib.request import urlopen
            ca_bytes = urlopen('https://raw.githubusercontent.com/cnk700i/havcs/master/custom_components/havcs/ca.crt').read()
            md5_l = hashlib.md5()
            md5_l.update(ca_bytes)
            latest_ca_md5 = md5_l.hexdigest()
            if local_ca_md5 != latest_ca_md5:
                _LOGGER.error('[init] can not connect to mqtt server(host = %s, port = %s, error_code = %s), update ca.crt.',broker, port, success)
            else:
                _LOGGER.error('[init] can not connect to mqtt server(host = %s, port = %s, error_code = %s), check mqtt server\'s address and port.',broker, port, success)
            return False
        async def async_stop_mqtt(event: Event):
            """Stop MQTT component."""
            await hass.data[DOMAIN][DATA_HAVCS_MQTT].async_disconnect()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_mqtt)

        async def async_http_proxy_handler(resData, topic, start_time = None):
            response = None
            url = ha_url + resData['uri']
            _LOGGER.debug('[http_proxy] request: url = %s', url)
            if('content' in resData):
                _LOGGER.debug('[http_proxy] use POST method')
                platform = resData.get('platform', havcs_util.get_platform_from_command(resData['content']))
                auth_type, auth_value = resData.get('headers', {}).get('Authorization',' ').split(' ', 1)
                _LOGGER.debug('[http_proxy] platform = %s, auth_type = %s, access_token = %s', platform, auth_type, auth_value)

                try:
                    session = async_get_clientsession(hass, verify_ssl=False)
                    with async_timeout.timeout(5, loop=hass.loop):
                        response = await session.post(url, data=resData['content'], headers = resData.get('headers'))
                except(asyncio.TimeoutError, aiohttp.ClientError):
                    _LOGGER.error("[http_proxy] fail to access %s in local network: timeout", url)
                except:
                    _LOGGER.error("[http_proxy] fail to access %s in local network: %s", url, traceback.format_exc())
            else:
                _LOGGER.debug('[http_proxy] use GET method')
                try:
                    session = async_get_clientsession(hass, verify_ssl=False)
                    with async_timeout.timeout(5, loop=hass.loop):
                        response = await session.get(url, headers = resData.get('headers'))
                except(asyncio.TimeoutError, aiohttp.ClientError):
                    _LOGGER.error("[http_proxy] fail to access %s in local network: timeout", url)
                except:
                    _LOGGER.error("[http_proxy] fail to access %s in local network: %s", url, traceback.format_exc())
                # _LOGGER.debug("[http_proxy] %s", response.history) #查看重定向信息
            if response is not None:
                if response.status != 200:
                    _LOGGER.error("[http_proxy] fail to access %s in local network: status=%d",url,response.status)
                if('image' in response.headers['Content-Type'] or 'stream' in response.headers['Content-Type']):
                    result = await response.read()
                    result = b64encode(result).decode()
                else:
                    result = await response.text()
                headers = {
                    'Content-Type': response.headers['Content-Type'] + ';charset=utf-8'
                }
                res = {
                    'headers': headers,
                    'status': response.status,
                    'content': result.encode('utf-8').decode('unicode_escape'),
                    'msgId': resData.get('msgId')
                }
                _LOGGER.debug("[http_proxy] response: uri = %s, msgid = %s, type = %s", resData['uri'].split('?')[0], resData.get('msgId'), response.headers['Content-Type'])
            else:
                res = {
                    'status': 500,
                    'content': '{"error":"time_out"}',
                    'msgId': resData.get('msgId')
                }
                _LOGGER.debug("[http_proxy] response: uri = %s, msgid = %s", resData['uri'].split('?')[0], resData.get('msgId'))
            res = havcs_util.AESCipher(decrypt_key).encrypt(json.dumps(res, ensure_ascii = False).encode('utf8'))

            await hass.data[DOMAIN][DATA_HAVCS_MQTT].async_publish(topic.replace('/request/','/response/'), res, 2, False)
            end_time = datetime.now()
            _LOGGER.debug('[mqtt] -------- mqtt task finish at %s, Running time: %ss --------', end_time.strftime('%Y-%m-%d %H:%M:%S'), (end_time - start_time).total_seconds())

        async def async_module_handler(resData, topic, start_time = None):
            platform = resData.get('platform', havcs_util.get_platform_from_command(resData['content']))
            if platform == 'unknown':
                _LOGGER.error('[skill] receive command from unsupport platform "%s".', platform)
                return
            if platform not in hass.data[DOMAIN][DATA_HAVCS_HANDLER]:
                _LOGGER.error('[skill] receive command from uninitialized platform "%s" , check up your configuration.yaml.', platform)
                return
            try:
                response = await hass.data[DOMAIN][DATA_HAVCS_HANDLER][platform].handleRequest(json.loads(resData['content']), auth = True)
            except:
                response = '{"error":"service error"}'
                _LOGGER.error('[skill] %s', traceback.format_exc())
            res = {
                    'headers': {'Content-Type': 'application/json;charset=utf-8'},
                    'status': 200,
                    'content': json.dumps(response).encode('utf-8').decode('unicode_escape'),
                    'msgId': resData.get('msgId')
                }
            res = havcs_util.AESCipher(decrypt_key).encrypt(json.dumps(res, ensure_ascii = False).encode('utf8'))

            await hass.data[DOMAIN][DATA_HAVCS_MQTT].async_publish(topic.replace('/request/','/response/'), res, 2, False)
            end_time = datetime.now()
            _LOGGER.debug('[mqtt] -------- mqtt task finish at %s, Running time: %ss --------', end_time.strftime('%Y-%m-%d %H:%M:%S'), (end_time - start_time).total_seconds())
            
        async def async_publish_error(resData,topic):
            res = {
                    'headers': {'Content-Type': 'application/json;charset=utf-8'},
                    'status': 404,
                    'content': '',
                    'msgId': resData.get('msgId')
                }                    
            res = havcs_util.AESCipher(decrypt_key).encrypt(json.dumps(res, ensure_ascii = False).encode('utf8'))
            await hass.data[DOMAIN][DATA_HAVCS_MQTT].async_publish(topic.replace('/request/','/response/'), res, 2, False)

        @callback
        def message_received(*args): # 0.90 传参变化
            if isinstance(args[0], str):
                topic = args[0]
                payload = args[1]
                # qos = args[2]
            else:
                topic = args[0].topic
                payload = args[0].payload
                # qos = args[0].qos
            """Handle new MQTT state messages."""
            # _LOGGER.debug('[mqtt] get encrypt message: \n {}'.format(payload))
            try:
                start_time = datetime.now()
                end_time = None
                _LOGGER.debug('[mqtt] -------- start handle task from mqtt at %s --------', start_time.strftime('%Y-%m-%d %H:%M:%S'))

                payload = havcs_util.AESCipher(decrypt_key).decrypt(payload)
                # _LOGGER.debug('[mqtt] get raw message: \n {}'.format(payload))
                req = json.loads(payload)
                if req.get('msgType') == 'hello':
                    _LOGGER.info('[mqtt] get hello message: %s', req.get('content'))
                    end_time = datetime.now() 
                    _LOGGER.debug('[mqtt] -------- mqtt task finish at %s, Running time: %ss --------', end_time.strftime('%Y-%m-%d %H:%M:%S'), (end_time - start_time).total_seconds())
                    return
                
                _LOGGER.debug("[mqtt] raw message: %s", req)
                if req.get('platform') == 'h2m2h':
                    if('http_proxy' not in MODE):
                        _LOGGER.info('[http_proxy] havcs not run in http_proxy mode, ignore request: %s', req)
                        raise RuntimeError
                    if(allowed_uri and req.get('uri','/').split('?')[0] not in allowed_uri):
                        _LOGGER.info('[http_proxy] uri not allowed: %s', req.get('uri','/'))
                        hass.add_job(async_publish_error(req, topic))
                        raise RuntimeError
                    hass.add_job(async_http_proxy_handler(req, topic, start_time))
                else:
                    if('skill' not in MODE):
                        _LOGGER.info('[skill] havcs not run in skill mode, ignore request: %s', req)
                        raise RuntimeError 
                    hass.add_job(async_module_handler(req, topic, start_time))

            except (JSONDecodeError, UnicodeDecodeError, binascii.Error):
                import sys
                ex_type, ex_val, ex_stack = sys.exc_info()
                log = ''
                for stack in traceback.extract_tb(ex_stack):
                    log += str(stack)
                _LOGGER.debug('[mqtt] fail to decrypt message, abandon[%s][%s]: %s', ex_type, ex_val, log)
                end_time = datetime.now()
            except:
                _LOGGER.error('[mqtt] fail to handle %s', traceback.format_exc())
                end_time = datetime.now()
            if end_time:    
                _LOGGER.debug('[mqtt] -------- mqtt task finish at %s, Running time: %ss --------', end_time.strftime('%Y-%m-%d %H:%M:%S'), (end_time - start_time).total_seconds())

        await hass.data[DOMAIN][DATA_HAVCS_MQTT].async_subscribe("ai-home/http2mqtt2hass/"+app_key+"/request/#", message_received, 2, 'utf-8')
        _LOGGER.info('[init] mqtt initialization finished, waiting for welcome message of mqtt server.')

    async def start_havcs(event: Event):
        async def async_load_device_info():
            _LOGGER.info('load device info from file')
            try:
                device_config = await hass.async_add_executor_job(
                    conf_util.load_yaml_config_file, havcd_config_path
                )
                hass.data[DOMAIN][DATA_HAVCS_ITEMS] = DEVICE_CONFIG_SCHEMA(device_config)
            except HomeAssistantError as err:
                _LOGGER.error("Error loading %s: %s", havcd_config_path, err)
                return None
            except VoluptuousError as exception:
                _LOGGER.warning("failed to load all devices from file, find invalid data: %s", exception)
            except:
                _LOGGER.error("Error loading %s: %s", havcd_config_path, traceback.format_exc())
                return None

        async def async_init_sub_entry():
            # create when config change
            mode = []
            if CONF_HTTP in conf:
                mode.append(CONF_HTTP)
                if CONF_HTTP_PROXY in conf:
                    mode.append(CONF_HTTP_PROXY)
            if CONF_SKILL in conf:
                mode.append(CONF_SKILL)

            havcs_entries = hass.config_entries.async_entries(DOMAIN)
            # sub entry for every platform
            entry_platforms = set([entry.data.get('platform') for entry in havcs_entries if entry.source == SOURCE_PLATFORM])
            conf_platforms = set(conf.get(CONF_PLATFORM))
            new_platforms = conf_platforms - entry_platforms
            _LOGGER.debug('[post-task] load new platform entry %s', new_platforms)
            for platform in new_platforms:
                # 如果在async_setup_entry中执行无法await，async_init所触发的component_setup会不断等待之前的component_setup任务
                await hass.async_create_task(hass.config_entries.flow.async_init(
                    DOMAIN, context={'source': SOURCE_PLATFORM},
                    data={'platform': platform, 'mode': mode}
                ))
            remove_platforms = entry_platforms - conf_platforms
            _LOGGER.debug('[post-task] remove old platform entry %s', remove_platforms)
            for entry in [entry for entry in havcs_entries if entry.source == SOURCE_PLATFORM]:
                if entry.data.get('platform') in remove_platforms:
                    await hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
                else:
                    entry.title=f"接入平台[{entry.data.get('platform')}-{DEVICE_PLATFORM_DICT[entry.data.get('platform')]['cn_name']}]，接入方式{mode}"
                    hass.config_entries.async_update_entry(entry)

            # await async_load_device_info()

            for platform in platforms:
                for ent in hass.config_entries.async_entries(DOMAIN):
                    if ent.source == SOURCE_PLATFORM and ent.data.get('platform') == platform:
                        try:
                            module = importlib.import_module('custom_components.{}.{}'.format(DOMAIN,platform))
                            _LOGGER.info('[post-task] import %s.%s', DOMAIN, platform)
                            hass.data[DOMAIN][DATA_HAVCS_HANDLER][platform] = module.createHandler(hass, ent)
                            # hass.data[DOMAIN][DATA_HAVCS_HANDLER][platform].vcdm.all(hass, True)
                        except ImportError as err:
                            _LOGGER.error('[post-task] Unable to import %s.%s, %s', DOMAIN, platform, err)
                            return False
                        except:
                            _LOGGER.error('[post-task] fail to create %s handler: %s',platform , traceback.format_exc())
                            return False
                        break
        await async_init_sub_entry()

        async def async_bind_device():
            for uuid in hass.data[DOMAIN][DATA_HAVCS_BIND_MANAGER].discovery:
                p_user_id = uuid.split('@')[0]
                platform = uuid.split('@')[1]
                if platform in hass.data[DOMAIN][DATA_HAVCS_HANDLER] and getattr(hass.data[DOMAIN][DATA_HAVCS_HANDLER].get(platform), 'should_report_when_starup', False) and hasattr(hass.data[DOMAIN][DATA_HAVCS_HANDLER].get(platform), 'bind_device'):
                    err_result, devices, entity_ids = hass.data[DOMAIN][DATA_HAVCS_HANDLER][platform].process_discovery_command()
                    if err_result:
                        return
                    bind_entity_ids, unbind_entity_ids = await hass.data[DOMAIN][DATA_HAVCS_BIND_MANAGER].async_save_changed_devices(entity_ids,platform, p_user_id,True)
                    payload = await hass.data[DOMAIN][DATA_HAVCS_HANDLER][platform].bind_device(p_user_id, entity_ids , unbind_entity_ids, devices)
                    _LOGGER.debug('[skill] bind device to %s:\nbind_entity_ids = %s, unbind_entity_ids = %s', platform, bind_entity_ids, unbind_entity_ids)

                    if payload:
                        url = HAVCS_SERVICE_URL + '/skill/smarthome.php?v=update&AppKey='+app_key
                        data = havcs_util.AESCipher(decrypt_key).encrypt(json.dumps(payload, ensure_ascii = False).encode('utf8'))
                        try:
                            session = async_get_clientsession(hass, verify_ssl=False)
                            with async_timeout.timeout(5, loop=hass.loop):
                                response = await session.post(url, data=data)
                                _LOGGER.debug('[skill] get bind device result from %s: %s', platform, await response.text())
                        except(asyncio.TimeoutError, aiohttp.ClientError):
                            _LOGGER.error("[skill] fail to access %s, bind device fail: timeout", url)
                        except:
                            _LOGGER.error("[skill] fail to access %s, bind device fail: %s", url, traceback.format_exc())

        if bind_device:
            await async_bind_device()

        @callback
        def report_device(event):
            # _LOGGER.debug('[skill] %s changed, try to report', event.data[ATTR_ENTITY_ID])
            hass.add_job(async_report_device(event))

        async def async_report_device(event):
            """report device state when changed. """
            entity = hass.states.get(event.data[ATTR_ENTITY_ID])
            if entity is None or not entity.attributes.get('havcs_device', False):
                return
            for platform, handler in hass.data[DOMAIN][DATA_HAVCS_HANDLER].items():
                if hasattr(handler, 'report_device'):
                    payload = hass.data[DOMAIN][DATA_HAVCS_HANDLER][platform].report_device(entity.entity_id)
                    _LOGGER.debug('[skill] report device to %s: platform = %s, entity_id = %s, data = %s', platform, event.data[ATTR_ENTITY_ID], platform, payload)
                    if payload:
                        url = HAVCS_SERVICE_URL + '/skill/'+platform+'.php?v=report&AppKey='+app_key
                        data = havcs_util.AESCipher(decrypt_key).encrypt(json.dumps(payload, ensure_ascii = False).encode('utf8'))
                        try:
                            session = async_get_clientsession(hass, verify_ssl=False)
                            with async_timeout.timeout(5, loop=hass.loop):
                                response = await session.post(url, data=data)
                                _LOGGER.debug('[skill] get report device result from %s: %s', platform, await response.text())
                        except(asyncio.TimeoutError, aiohttp.ClientError):
                            _LOGGER.error("[skill] fail to access %s, report device fail: timeout", url)
                        except:
                            _LOGGER.error("[skill] fail to access %s, report device fail: %s", url, traceback.format_exc())       

        if sync_device:
            hass.bus.async_listen(EVENT_STATE_CHANGED, report_device)

        if DATA_HAVCS_MQTT in hass.data[DOMAIN]:
            await hass.data[DOMAIN][DATA_HAVCS_MQTT].async_publish("ai-home/http2mqtt2hass/"+app_key+"/response/test", 'init', 2, False)

        async def async_handler_service(service):
    
            if service.service == SERVICE_RELOAD:
                await async_load_device_info()
                for platform in hass.data[DOMAIN][DATA_HAVCS_HANDLER]:
                    devices = hass.data[DOMAIN][DATA_HAVCS_HANDLER][platform].vcdm.all(hass, True)
                    await hass.data[DOMAIN][DATA_HAVCS_HANDLER][platform].vcdm.async_reregister_devices(hass)
                    _LOGGER.info('[service] ------------%s 平台加载设备信息------------\n%s', platform, [device.attributes for device in devices])
                    mind_devices = [device.attributes for device in devices if None in device.attributes.values() or [] in device.attributes.values()]
                    if mind_devices:
                        _LOGGER.debug('!!!!!!!! 以下设备信息不完整，检查值为None或[]的属性并进行设置 !!!!!!!!')
                        for mind_device in mind_devices:
                            _LOGGER.debug('%s', mind_device)
                    _LOGGER.info('[service] ------------%s 平台加载设备信息------------\n', platform)
                if bind_device:
                    await async_bind_device()

            elif service.service == SERVICE_DEBUG_DISCOVERY:
                for platform, handler in hass.data[DOMAIN][DATA_HAVCS_HANDLER].items():
                    err_result, discovery_devices, entity_ids = handler.process_discovery_command()
                    _LOGGER.info('[service][%s] trigger discovery command, response: %s', platform, discovery_devices)
            else:
                pass
        hass.services.async_register(DOMAIN, SERVICE_RELOAD, async_handler_service, schema=HAVCS_SERVICE_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_DEBUG_DISCOVERY, async_handler_service, schema=HAVCS_SERVICE_SCHEMA)

        await hass.services.async_call(DOMAIN, SERVICE_RELOAD)

    if config_entry.source == config_entries.SOURCE_IMPORT:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_havcs)
    elif config_entry.source == config_entries.SOURCE_USER:
        hass.async_create_task(start_havcs(None))

    _LOGGER.info('[init] havcs initialization finished.')
    return True

async def async_unload_entry(hass, config_entry):
    if config_entry.source in [config_entries.SOURCE_IMPORT, config_entries.SOURCE_USER]:
        tasks = [hass.config_entries.async_remove(entry.entry_id) for entry in hass.config_entries.async_entries(DOMAIN) if entry.source == SOURCE_PLATFORM and entry.data['platform'] in config_entry.data['platform']]
        if tasks:
            unload_ok = all(await asyncio.gather(*tasks))
        else:
            unload_ok =True
        if unload_ok:
            hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
            hass.services.async_remove(DOMAIN, SERVICE_DEBUG_DISCOVERY)
            if DATA_HAVCS_MQTT in hass.data[DOMAIN]:
                await hass.data[DOMAIN][DATA_HAVCS_MQTT].async_disconnect()
                hass.data[DOMAIN].pop(DATA_HAVCS_MQTT)
            hass.data[DOMAIN].pop(DATA_HAVCS_BIND_MANAGER)
            hass.data[DOMAIN].pop(DATA_HAVCS_CONFIG)
            hass.data[DOMAIN].pop(DATA_HAVCS_ITEMS)
            hass.data[DOMAIN].pop(DATA_HAVCS_HANDLER)
            hass.data[DOMAIN].pop(CONF_DEVICE_CONFIG)
            hass.components.frontend.async_remove_panel(DOMAIN)
            if not hass.data[DOMAIN]:
                hass.data.pop(DOMAIN)
        return unload_ok

    elif config_entry.source == SOURCE_PLATFORM:
        for entry in [entry for entry in hass.config_entries.async_entries(DOMAIN) if entry.source in [config_entries.SOURCE_IMPORT, config_entries.SOURCE_USER]]:
            if config_entry.data['platform'] in entry.data['platform']:
                entry.data['platform'].remove(config_entry.data['platform'])
        return True

class HavcsGateView(HomeAssistantView):
    """View to handle Configuration requests."""

    url = '/havcs_service'
    name = 'havcs_service'
    requires_auth = False    # 不使用HA内置方法验证(request头带token)，在handleRequest()中再验证

    def __init__(self, hass):
        self._hass = hass
        """Initialize the token view."""

    async def post(self, request):
        """Update state of entity."""
        try:
            start_time = datetime.now()
            _LOGGER.debug('[http] -------- start handle task from http at %s --------', start_time.strftime('%Y-%m-%d %H:%M:%S'))
            data = await request.text()
            _LOGGER.debug('[http] raw message: %s', data)
            platform = havcs_util.get_platform_from_command(data)
            auth_value = havcs_util.get_token_from_command(data)
            _LOGGER.debug('[http] get access_token >>> %s <<<', auth_value)
            refresh_token = await self._hass.auth.async_validate_access_token(auth_value)
            if refresh_token:
                _LOGGER.debug('[http] validate access_token, get refresh_token(id = %s)', refresh_token.id)
            else:
                _LOGGER.debug('[http] validate access_token, get None')
                _LOGGER.debug('[http] !!! token校验失败，请检查授权 !!!')
            response = await self._hass.data[DOMAIN][DATA_HAVCS_HANDLER][platform].handleRequest(json.loads(data), refresh_token)
        except:
            _LOGGER.error('[http] handle fail: %s', traceback.format_exc())
            response = {}
        finally:
            end_time = datetime.now()
            _LOGGER.debug('[http] -------- http task finish at %s, running time: %ss --------', end_time.strftime('%Y-%m-%d %H:%M:%S'), (end_time - start_time).total_seconds())
        return self.json(response)

class HavcsAuthView(HomeAssistantView):
    """View to handle Configuration requests."""

    url = '/havcs_auth'
    name = 'havcs_auth'
    requires_auth = False

    def __init__(self, hass, ha_url):
        self._hass = hass
        self._havcs_auth_url = ha_url + '/havcs_auth'
        self._token_url = ha_url + '/auth/token'
        self._client_id = ha_url

    async def post(self, request):
        headers = request.headers
        _LOGGER.debug('[auth] request headers : %s', headers)
        body_data = await request.text()
        _LOGGER.debug('[auth] request data : %s', body_data)
        try:
            data = json.loads(body_data)
        except JSONDecodeError:
            query_string = body_data if body_data else request.query_string
            _LOGGER.debug('[auth] request query : %s', query_string)
            data = { k:v[0] for k, v in parse.parse_qs(query_string).items() }   
        except:
            _LOGGER.error('[auth] handle request : %s', traceback.format_exc() )

        # self._platform_uri = data.get('redirect_uri')
        # data['redirect_uri'] = self._havcs_auth_url
        _LOGGER.debug('[auth] forward request: data = %s', data)
        grant_type = data.get('grant_type')
        try:
            session = async_get_clientsession(self._hass, verify_ssl=False)
            with async_timeout.timeout(5, loop=self._hass.loop):
                response = await session.post(self._token_url, data=data)
        except(asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("[auth] fail to get token, access %s in local network: timeout", self._token_url)
        except:
            _LOGGER.error("[auth] fail to get token, access %s in local network: %s", self._token_url, traceback.format_exc())

        if grant_type == 'authorization_code':
            try:
                result = await response.json()
                result['expires_in'] = int(EXPIRATION.total_seconds())
                _LOGGER.debug('[auth] get access token[%s] with default expiration, try to update expiration param and get new access token through another refresh token request.', result.get('access_token'))
                access_token = result.get('access_token')
                await havcs_util.async_update_token_expiration(access_token, self._hass, EXPIRATION)

                try:
                    refresh_token_data = {'client_id': data.get('client_id'), 'grant_type': 'refresh_token', 'refresh_token': result.get('refresh_token')}
                    session = async_get_clientsession(self._hass, verify_ssl=False)
                    with async_timeout.timeout(5, loop=self._hass.loop):
                        response = await session.post(self._token_url, data=refresh_token_data)
                except(asyncio.TimeoutError, aiohttp.ClientError):
                    _LOGGER.error("[auth] fail to get new access token, access %s in local network: timeout", self._token_url)
                    return web.Response(status=response.status)
                
                try:
                    refresh_token_result = await response.json()
                    _LOGGER.debug('[auth] get new access token[%s] with new expiration.', refresh_token_result.get('access_token'))
                    result['access_token'] = refresh_token_result.get('access_token')
                    _LOGGER.debug('[auth] success to deal %s request, return access token.', grant_type)
                    return self.json(result)
                except:
                    result = await response.text()
                    _LOGGER.error("[auth] fail to get new access token, access %s in local network, get response: status = %s, data = %s", self._token_url, response.status, result)
                    return web.Response(status=response.status)
            except:
                result = await response.text()
                _LOGGER.error("[auth] fail to get token from %s in local network, get response: status = %s, data = %s", self._token_url, response.status, result)
                return web.Response(status=response.status)
        elif grant_type == 'refresh_token':
            try:
                result = await response.json()
                result['refresh_token'] = data.get('refresh_token')
                _LOGGER.debug("[auth] deal %s request, return refresh_token again: status = %s, data = %s", grant_type, response.status, result)
                return self.json(result)
            except:
                result = await response.text()
                _LOGGER.error("[auth] fail to deal %s request, get response: status = %s, data = %s", grant_type, response.status, result)
                return web.Response(status=response.status)        
        else:
            try:
                result = await response.json()
                _LOGGER.debug("[auth] success to deal %s request, get response: status = %s, data = %s", grant_type, response.status, result)
                return self.json(result)
            except:
                result = await response.text()
                _LOGGER.error("[auth] fail to deal %s request, get response: status = %s, data = %s", grant_type, response.status, result)
                return web.Response(status=response.status)
        # return web.Response( headers={'Location': self._auth_url+'?'+query_string}, status=303)

class HavcsTestView(HomeAssistantView):
    # url = r'/havcs_test/{parama:\w+}'
    url = '/havcs_test'
    name = 'havcs_test'
    requires_auth = False

    async def head(self, request):
        return

class HavcsDeviceView(HomeAssistantView):
    url = '/havcs_device'
    name = 'havcs_device'
    requires_auth = True

    def __init__(self, hass):
        self._hass = hass
        local = hass.config.path("custom_components/" + DOMAIN + "/html")
        if os.path.isdir(local):
            hass.http.register_static_path('/havcs', local, False)
        hass.components.frontend.async_register_built_in_panel(
            component_name = "iframe",
            sidebar_title = 'HAVCS设备',
            sidebar_icon = 'mdi:home-edit',
            frontend_url_path = DOMAIN,
            config = {"url": '/havcs/index.html'},
            require_admin=True
        )

    async def post(self, request):
        req = await request.json()
        action = req.get('action')
        if action == 'getList':
            device_list = [ {**{'device_id': device_id}, **device_attributes} for device_id, device_attributes in self._hass.data[DOMAIN][DATA_HAVCS_ITEMS].items()]
            return self.json({ 'code': 'ok', 'Msg': '获取成功', 'data': device_list})
        elif action == 'get':
            device_id = req.get('device_id')
            device = self._hass.data[DOMAIN][DATA_HAVCS_ITEMS].get(device_id)
            if device:
                return self.json({ 'code': 'ok', 'Msg': '获取成功', 'data': {**{'device_id': device_id}, **device}})
        elif action == 'getDict':
            dict_names = req.get('data')
            data = {}
            for dict_name in dict_names:
                dict_data = globals().get('DEVICE_' + dict_name.upper() + '_DICT')
                data.update({dict_name: dict_data})
            return self.json({ 'code': 'ok', 'Msg': '获取成功', 'data':data})
        elif action == 'delete':
            device_id = req.get('device_id')
            self._hass.data[DOMAIN][DATA_HAVCS_ITEMS].pop(device_id)
            save_yaml(self._hass.data[DOMAIN][CONF_DEVICE_CONFIG], self._hass.data[DOMAIN][DATA_HAVCS_ITEMS])
            return self.json({ 'code': 'ok', 'Msg': '执行成功', 'data':{'device_id': device_id}})
        elif action == 'update':
            device = req.get('device')
            device_id = device.pop('device_id')
            if device_id:
                self._hass.data[DOMAIN][DATA_HAVCS_ITEMS].setdefault(device_id, {})
                # self._hass.data[DOMAIN][DATA_HAVCS_ITEMS][device_id].update(device)
                self._hass.data[DOMAIN][DATA_HAVCS_ITEMS][device_id].update(device)
                save_yaml(self._hass.data[DOMAIN][CONF_DEVICE_CONFIG], self._hass.data[DOMAIN][DATA_HAVCS_ITEMS])
                return self.json({ 'code': 'ok', 'Msg': '执行成功', 'data':{'device_id': device_id}})
        return self.json({ 'code': 'error', 'Msg': '请求'+action+'失败'})