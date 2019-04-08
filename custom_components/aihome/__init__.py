"""
author: cnk700i
blog: ljr.im
tested On HA version: 0.90.2
"""
from . import util as aihome_util
from typing import cast
import jwt
from datetime import timedelta
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
from . import config_flow
from voluptuous.humanize import humanize_error
import traceback

import asyncio
import async_timeout
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['paho-mqtt>=1.4.0']

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)

DOMAIN = 'aihome'
HANDLER = {}
EXPIRATION = {}

DATA_AIHOME_CONFIG = 'aihome_config'
DATA_AIHOME_MQTT = 'aihome_mqtt'
DATA_AIHOME_BIND_MANAGER = 'aihome_bind_manager'

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
CONF_SYNC = 'sync'

CONF_HTTP = 'http'
CONF_MQTT = 'mqtt'
CONF_PLATFORM = 'platform'
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
DEFAULT_HA_URL = 'https://localhost:8123'
DEFAULT_ALLOWED_URI = []
# DEFAULT_ALLOWED_URI = ['/auth/token', '/dueros_gate', '/aligenie_gate', '/jdwhale_gate']

CLIENT_KEY_AUTH_MSG = 'client_key and client_cert must both be present in the MQTT broker configuration'

MQTT_SCHEMA = vol.Schema({
        vol.Optional(CONF_CLIENT_ID): cv.string,
        vol.Optional(CONF_KEEPALIVE, default=DEFAULT_KEEPALIVE): vol.All(vol.Coerce(int), vol.Range(min=15)),
        vol.Optional(CONF_BROKER, default=DEFAULT_BROKER): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_APP_KEY): cv.string,
        vol.Required(CONF_APP_SECRET): cv.string,
        vol.Optional(CONF_CERTIFICATE): vol.Any('auto', cv.isfile),
        vol.Inclusive(CONF_CLIENT_KEY, 'client_key_auth', msg=CLIENT_KEY_AUTH_MSG): cv.isfile,
        vol.Inclusive(CONF_CLIENT_CERT, 'client_key_auth', msg=CLIENT_KEY_AUTH_MSG): cv.isfile,
        vol.Optional(CONF_TLS_INSECURE, default=True): cv.boolean,
        vol.Optional(CONF_TLS_VERSION, default=DEFAULT_TLS_PROTOCOL): vol.Any('auto', '1.0', '1.1', '1.2'),
        vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.All(cv.string, vol.In([PROTOCOL_31, PROTOCOL_311])),
        vol.Optional(CONF_TOPIC): cv.string,
        vol.Optional(CONF_ALLOWED_URI, default=DEFAULT_ALLOWED_URI): vol.All(cv.ensure_list, vol.Length(min=0), [cv.string]),
        vol.Required(CONF_ENTITY_KEY):vol.All(cv.string, vol.Length(min=16, max=16)),
        vol.Optional(CONF_USER_ID): cv.string,
        vol.Optional(CONF_HA_URL, default=DEFAULT_HA_URL): cv.string,
        vol.Optional(CONF_SYNC, default=False): cv.boolean,
}, extra=vol.ALLOW_EXTRA)
HTTP_SCHEMA = vol.Schema({
    vol.Optional(CONF_EXPIRE_IN_HOURS, default=DEFAULT_EXPIRE_IN_HOURS): cv.positive_int
}, extra=vol.ALLOW_EXTRA)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PLATFORM): vol.All(cv.ensure_list, vol.Length(min=1), ['jdwhale', 'aligenie', 'dueros']),
        vol.Optional(CONF_HTTP): HTTP_SCHEMA,
        vol.Optional(CONF_MQTT): MQTT_SCHEMA,
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:

    conf = config.get(DOMAIN, {})  # type: ConfigType
 
    if conf is None:
        # If we have a config entry, setup is done by that config entry.
        # If there is no config entry, this should fail.
        return bool(hass.config_entries.async_entries(DOMAIN))

    hass.data[DATA_AIHOME_CONFIG] = conf

    # Only import if we haven't before.
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
            data={}
        ))
    if CONF_MQTT in conf:            
        aihome_util.ENTITY_KEY = conf.get(CONF_MQTT).get(CONF_ENTITY_KEY)
    if CONF_USER_ID in conf:
        aihome_util.CONTEXT_AIHOME = Context(conf.get(CONF_MQTT).get(CONF_USER_ID))

    global EXPIRATION
    platform = conf[CONF_PLATFORM]
    manager = hass.data[DATA_AIHOME_BIND_MANAGER] = aihome_util.BindManager(hass,platform)
    await manager.async_load()

    for p in platform:
        if CONF_HTTP in conf:
            _LOGGER.debug('http: %s', p)
            module = importlib.import_module('custom_components.{}.{}'.format(DOMAIN,p))
            if hasattr(module, 'AI_HOME'):
                await module.async_setup(hass, config)
            elif p == 'dueros':
                setattr(module, '_hass', hass)
                view = getattr(module, 'DuerosGateView')()
                hass.http.register_view(view)
            elif p == 'aligenie':
                setattr(module, '_hass', hass)
                view = getattr(module, 'AliGenieGateView')()
                hass.http.register_view(view)
            EXPIRATION[p] = timedelta(hours=conf[CONF_HTTP].get(CONF_EXPIRE_IN_HOURS))
        if CONF_MQTT in conf:
            module = importlib.import_module('custom_components.{}.{}'.format(DOMAIN,p))
            if module.AI_HOME is not None:
                HANDLER[p] = module.createHandler(hass)
            else:
                HANDLER[p] = module

    return True

async def async_setup_entry(hass, entry):
    """Load a config entry."""
    conf = hass.data.get(DATA_AIHOME_CONFIG).get(CONF_MQTT)

    # Config entry was created because user had configuration.yaml entry
    # They removed that, so remove entry.
    if conf is None and entry.source == config_entries.SOURCE_IMPORT:
        hass.async_create_task(
            hass.config_entries.async_remove(entry.entry_id))
        return False

    # If user didn't have configuration.yaml config, generate defaults
    if conf is None:
        conf = CONFIG_SCHEMA({
            DOMAIN: entry.data,
        })[DOMAIN].get(CONF_MQTT)
    elif any(key in conf for key in entry.data):
        _LOGGER.warning(
            "Data in your config entry is going to override your "
            "configuration.yaml: %s", entry.data)

    conf.update(entry.data)

    broker = conf[CONF_BROKER]
    port = conf[CONF_PORT]
    client_id = conf.get(CONF_CLIENT_ID)
    keepalive = conf[CONF_KEEPALIVE]
    app_key = conf.get(CONF_APP_KEY)
    app_secret = conf.get(CONF_APP_SECRET)
    certificate = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ca.crt')
    if os.path.exists(certificate):
        _LOGGER.info('auto load ca.crt from %s', certificate)
    else:
        certificate = conf.get(CONF_CERTIFICATE)
    client_key = conf.get(CONF_CLIENT_KEY)
    client_cert = conf.get(CONF_CLIENT_CERT)
    tls_insecure = conf.get(CONF_TLS_INSECURE)
    protocol = conf[CONF_PROTOCOL]
    allowed_uri = conf.get(CONF_ALLOWED_URI)
    _LOGGER.info('allowed_uri: %s', allowed_uri)
    ha_url = conf.get(CONF_HA_URL)
    sync = conf.get(CONF_SYNC)
    decrypt_key =bytes().fromhex(sha1(app_secret.encode("utf-8")).hexdigest())[0:16]

    # For cloudmqtt.com, secured connection, auto fill in certificate
    if (certificate is None and 19999 < conf[CONF_PORT] < 30000 and
            broker.endswith('.cloudmqtt.com')):
        certificate = os.path.join(
            os.path.dirname(__file__), 'addtrustexternalcaroot.crt')

    # When the certificate is set to auto, use bundled certs from requests
    elif certificate == 'auto':
        certificate = requests.certs.where()

    if CONF_WILL_MESSAGE in conf:
        will_message = mqtt.Message(**conf[CONF_WILL_MESSAGE])
    else:
        will_message = None

    if CONF_BIRTH_MESSAGE in conf:
        birth_message = mqtt.Message(**conf[CONF_BIRTH_MESSAGE])
    else:
        birth_message = None

    # Be able to override versions other than TLSv1.0 under Python3.6
    conf_tls_version = conf.get(CONF_TLS_VERSION)  # type: str
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

    hass.data[DATA_AIHOME_MQTT] = mqtt.MQTT(
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

    success = await hass.data[DATA_AIHOME_MQTT].async_connect()  # type: bool

    if not success:
        _LOGGER.error('can not connect to mqtt server, check mqtt server\'s address and port.')
        return False

    async def start_aihome(event: Event):
        async def async_bind_device():
            for uuid in hass.data['aihome_bind_manager'].discovery:
                p_user_id = uuid.split('@')[0]
                platform = uuid.split('@')[1]
                if platform in HANDLER and getattr(HANDLER.get(platform), 'should_report_when_starup', False) and hasattr(HANDLER.get(platform), 'bind_device'):
                    devices,entity_ids = HANDLER[platform]._discoveryDevice()
                    bind_entity_ids,unbind_entity_ids = await hass.data['aihome_bind_manager'].async_save_changed_devices(entity_ids,platform, p_user_id,True)
                    payload = await HANDLER[platform].bind_device(p_user_id, entity_ids , unbind_entity_ids, devices)
                    _LOGGER.debug('[%s] report request: bind_entity_ids:%s, unbind_entity_ids:%s', platform, bind_entity_ids, unbind_entity_ids)

                    if payload:
                        url = 'https://ai-home.ljr.im/skill/smarthome.php?v=update&AppKey='+app_key
                        data = aihome_util.AESCipher(decrypt_key).encrypt(json.dumps(payload, ensure_ascii = False).encode('utf8'))
                        try:
                            session = async_get_clientsession(hass, verify_ssl=False)
                            with async_timeout.timeout(5, loop=hass.loop):
                                response = await session.post(url, data=data)
                                _LOGGER.debug('[%s] report response:%s', platform, await response.text())
                        except(asyncio.TimeoutError, aiohttp.ClientError):
                            _LOGGER.error("Error while accessing: %s", url)
        await async_bind_device()

        @callback
        def report_device(event):
            _LOGGER.debug('%s changed', event.data[ATTR_ENTITY_ID])
            hass.add_job(async_report_device(event))

        async def async_report_device(event):
            """report device state when changed. """
            entity = hass.states.get(event.data[ATTR_ENTITY_ID])
            if not entity.attributes.get('aihome_device', False):
                return
            for platform, handler in HANDLER.items():
                if hasattr(handler, 'report_device'):
                    payload = HANDLER[platform].report_device(entity.entity_id)
                    _LOGGER.debug('[%s] report device: %s, %s, %s', platform, event.data[ATTR_ENTITY_ID], platform, payload)
                    if payload:
                        url = 'https://ai-home.ljr.im/skill/'+platform+'.php?v=report&AppKey='+app_key
                        data = aihome_util.AESCipher(decrypt_key).encrypt(json.dumps(payload, ensure_ascii = False).encode('utf8'))
                        try:
                            session = async_get_clientsession(hass, verify_ssl=False)
                            with async_timeout.timeout(5, loop=hass.loop):
                                response = await session.post(url, data=data)
                                _LOGGER.debug('[%s] report response:%s', platform, await response.text())
                        except(asyncio.TimeoutError, aiohttp.ClientError):
                            _LOGGER.error("Error while accessing: %s", url)

        if sync:
            hass.bus.async_listen(EVENT_STATE_CHANGED, report_device)

        await hass.data[DATA_AIHOME_MQTT].async_publish("ai-home/http2mqtt2hass/"+app_key+"/response/test", 'init', 2, False)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_aihome)

    async def async_stop_mqtt(event: Event):
        """Stop MQTT component."""
        await hass.data[DATA_AIHOME_MQTT].async_disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_mqtt)

    async def async_http_handler(resData,topic):
        url = ha_url + resData['uri']
        if('content' in resData):
            _LOGGER.debug('---POST---')
            if 'AliGenie' in resData['content']:
                platform = 'aligenie'
            elif 'DuerOS' in resData['content']:
                platform = 'dueros'
            elif 'Alpha' in resData['content']:
                platform = 'jdwhale'
            else:
                platform = 'unknown'
            if platform in EXPIRATION:
                auth_type, auth_value = resData['headers'].get('Authorization').split(' ', 1)
                try:
                    unverif_claims = jwt.decode(auth_value, verify=False)
                    refresh_token = await hass.auth.async_get_refresh_token(cast(str, unverif_claims.get('iss')))
                    if refresh_token is not None:
                        refresh_token.access_token_expiration = EXPIRATION[platform]
                        for user in hass.auth._store._users.values():
                            if refresh_token.id in user.refresh_tokens:
                                user.refresh_tokens[refresh_token.id] = refresh_token
                                hass.auth._store._async_schedule_save()
                                EXPIRATION.pop(platform)
                                break
                except jwt.InvalidTokenError:
                    pass
 
            try:
                session = async_get_clientsession(hass, verify_ssl=False)
                with async_timeout.timeout(5, loop=hass.loop):
                    response = await session.post(url, data=resData['content'], headers = resData.get('headers'))
            except(asyncio.TimeoutError, aiohttp.ClientError):
                _LOGGER.error("Error while accessing: %s", url)

        else:
            _LOGGER.debug('---GET---')
            try:
                session = async_get_clientsession(hass, verify_ssl=False)
                with async_timeout.timeout(5, loop=hass.loop):
                    response = await session.get(url, headers = resData.get('headers'))
            except(asyncio.TimeoutError, aiohttp.ClientError):
                _LOGGER.error("Error while accessing: %s", url)
            # _LOGGER.debug(response.history) #查看重定向信息
        if response is not None:
            if response.status != 200:
                _LOGGER.error("Error while accessing: %s, status=%d",url,response.status)
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
        else:
            res = {
                'status': 500,
                'content': '{"error":"time_out"}',
                'msgId': resData.get('msgId')
            }
        _LOGGER.debug("%s response[%s]: [%s]", resData['uri'].split('/')[-1].split('?')[0], resData.get('msgId'), response.headers['Content-Type'], )
        res = aihome_util.AESCipher(decrypt_key).encrypt(json.dumps(res, ensure_ascii = False).encode('utf8'))

        await hass.data[DATA_AIHOME_MQTT].async_publish(topic.replace('/request/','/response/'), res, 2, False)

    async def async_module_handler(resData,topic):
        if 'platform' in resData:
            platform = resData['platform']
        elif 'AliGenie' in resData['content']:
            platform = 'aligenie'
        elif 'DuerOS' in resData['content']:
            platform = 'dueros'
        elif 'Alpha' in resData['content']:
            platform = 'jdwhale'
        else:
            platform = 'unknown'
            _LOGGER.error('receive command from unsupport platform "%s".', platform)
            return
        if platform not in HANDLER:
            _LOGGER.error('receive command from uninitialized platform "%s" , check up your configuration.yaml.', platform)
            return
        try:
            response = await HANDLER[platform].handleRequest(json.loads(resData['content']), ignoreToken = True)
        except:
            response = '{"error":"service error"}'
            import traceback
            _LOGGER.error(traceback.format_exc())
        res = {
                'headers': {'Content-Type': 'application/json;charset=utf-8'},
                'status': 200,
                'content': json.dumps(response).encode('utf-8').decode('unicode_escape'),
                'msgId': resData.get('msgId')
            }
        res = aihome_util.AESCipher(decrypt_key).encrypt(json.dumps(res, ensure_ascii = False).encode('utf8'))

        await hass.data[DATA_AIHOME_MQTT].async_publish(topic.replace('/request/','/response/'), res, 2, False)
        
    async def async_publish_error(resData,topic):
        res = {
                'headers': {'Content-Type': 'application/json;charset=utf-8'},
                'status': 404,
                'content': '',
                'msgId': resData.get('msgId')
            }                    
        res = aihome_util.AESCipher(decrypt_key).encrypt(json.dumps(res, ensure_ascii = False).encode('utf8'))
        await hass.data[DATA_AIHOME_MQTT].async_publish(topic.replace('/request/','/response/'), res, 2, False)

    @callback
    def message_received(*args): # 0.90 传参变化
        if isinstance(args[0], str):
            topic = args[0]
            payload = args[1]
            qos = args[2]
        else:
            topic = args[0].topic
            payload = args[0].payload
            qos = args[0].qos
        """Handle new MQTT state messages."""
        # _LOGGER.debug('get encrypt message: \n {}'.format(payload))
        try:
            payload = aihome_util.AESCipher(decrypt_key).decrypt(payload)
            req = json.loads(payload)
            if req.get('msgType') == 'hello':
                _LOGGER.info(req.get('content'))
                return
            _LOGGER.debug("[%s] raw message: %s", req.get('platform'), req)
            if req.get('platform') == 'h2m2h':
                if(allowed_uri and req.get('uri','/').split('?')[0] not in allowed_uri):
                    _LOGGER.debug('uri not allowed: %s', req.get('uri','/'))
                    hass.add_job(async_publish_error(req, topic))
                    return
                hass.add_job(async_http_handler(req, topic))
            else:
                hass.add_job(async_module_handler(req, topic))

        except (JSONDecodeError,UnicodeDecodeError,binascii.Error):
            import sys
            ex_type, ex_val, ex_stack = sys.exc_info()
            log = ''
            for stack in traceback.extract_tb(ex_stack):
                log += str(stack)
            _LOGGER.debug('decrypt failure, abandon:%s', log)

    await hass.data[DATA_AIHOME_MQTT].async_subscribe("ai-home/http2mqtt2hass/"+app_key+"/request/#", message_received, 2, 'utf-8')
    return True
