
from aiohttp import web
import asyncio
import aiohttp
from datetime import datetime, timedelta
from urllib import parse
import async_timeout
import os
import json
from urllib.parse import urlparse, urlencode
from homeassistant.util.yaml import save_yaml, loader
from voluptuous import error as er
import yaml
import traceback
import logging

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.frontend import DATA_PANELS
from .const import DATA_HAVCS_HANDLER, INTEGRATION, DATA_HAVCS_ITEMS, CONF_DEVICE_CONFIG_PATH, DATA_HAVCS_CONFIG, HAVCS_SERVICE_URL, CLIENT_PALTFORM_DICT, DEVICE_TYPE_DICT, DEVICE_PLATFORM_DICT, DEVICE_ATTRIBUTE_DICT, DEVICE_ACTION_DICT
from . import util as havcs_util

from multidict import MultiDict

_LOGGER = logging.getLogger(__name__)
LOGGER_NAME = 'http'

class HavcsServiceView(HomeAssistantView):
    """View to handle Configuration requests."""

    url = '/havcs/service'
    name = 'havcs:service'
    requires_auth = False    # 不使用HA内置方法验证(request头带token)，在handleRequest()中再验证

    def __init__(self, hass):
        self._hass = hass
        """Initialize the token view."""

    async def post(self, request):
        """Update state of entity."""
        try:
            start_time = datetime.now()
            _LOGGER.debug("[%s] -------- start handle task from http at %s --------", LOGGER_NAME, start_time.strftime('%Y-%m-%d %H:%M:%S'))
            data = await request.text()
            _LOGGER.debug("[%s] raw message: %s", LOGGER_NAME, data)
            platform = havcs_util.get_platform_from_command(data)
            auth_value = havcs_util.get_token_from_command(data)
            _LOGGER.debug("[%s] get access_token >>> %s <<<", LOGGER_NAME, auth_value)
            refresh_token = await self._hass.auth.async_validate_access_token(auth_value)
            if refresh_token:
                _LOGGER.debug("[%s] validate access_token, get refresh_token(id = %s)", LOGGER_NAME, refresh_token.id)
            else:
                _LOGGER.debug("[%s] validate access_token, get None", LOGGER_NAME)
                _LOGGER.debug("[%s] !!! token校验失败，请检查授权 !!!", LOGGER_NAME)
            response = await self._hass.data[INTEGRATION][DATA_HAVCS_HANDLER][platform].handleRequest(json.loads(data), refresh_token)
        except:
            _LOGGER.error("[%s] handle fail: %s", LOGGER_NAME, traceback.format_exc())
            response = {}
        finally:
            end_time = datetime.now()
            _LOGGER.debug("[%s] -------- http task finish at %s, running time: %ss --------", LOGGER_NAME, end_time.strftime('%Y-%m-%d %H:%M:%S'), (end_time - start_time).total_seconds())
        return self.json(response)

class HavcsAuthorizeView(HomeAssistantView):
    url = '/havcs/auth/authorize'
    name = 'havcs:auth:authorize'
    requires_auth = False

    def __init__(self, hass, ha_url):
        self._hass = hass
        self._ha_url = ha_url
        self._authorize_url = ha_url + self.url
        self._flow_id = None
        self._login_attempts = {}

    async def head(self, request):
        return

    async def get(self, request):
        client_id = request.query.get('client_id')
        if client_id in self._hass.data[INTEGRATION][DATA_HAVCS_CONFIG].get('http', {}).get('clients', {}).keys():
            with open(self._hass.config.path("custom_components/" + INTEGRATION + "/html/login.html"), mode="r", encoding='UTF-8') as f:
                body = f.read()
            return web.Response(body=body, content_type='text/html')
        return web.Response(body='401 ?(￣△￣?) 参数不全拒绝访问 (?￣△￣)?', status=401)

    async def post(self, request):
        remote_addr = request.get('ha_real_ip')
        login_attemp = self._login_attempts.setdefault(remote_addr, {'count': 0, 'first_time': None, 'last_time': datetime.now()})
        req = await request.post()
        client_id = request.query.get('client_id')
        redirect_uri = request.query.get('redirect_uri')
        state = request.query.get('state')
        username = req.get('username')
        password = req.get('password')
        if not all((client_id, redirect_uri, username, password)):
            return web.Response(body='400 ?(￣△￣?) 参数不全拒绝访问 (?￣△￣)?', status=400)
        parts = urlparse(redirect_uri)
        if not any([client_id.startswith(platform) and parts.scheme + '://' + parts.netloc == CLIENT_PALTFORM_DICT[platform] for platform in CLIENT_PALTFORM_DICT.keys()]):
            return web.Response(body='400 ?(￣△￣?) 参数不全拒绝访问 (?￣△￣)?', status=400)
        if datetime.now() - login_attemp['last_time'] > timedelta(minutes=1):
            login_attemp['count'] = 0
        if login_attemp['count'] >= 5 and datetime.now() - login_attemp['first_time'] < timedelta(minutes=1):
            _LOGGER.info("[%s][auth]Too many login attempts Login attempt with invalid authentication", LOGGER_NAME)
            return web.Response(body='403 (╯‵□′)╯︵ ┴─┴ 失败尝试次数过多暂时拉入小黑屋', status=403)
        
        client_id = parts.scheme + '://' + parts.netloc
        data = {
            "client_id": client_id,
            "handler": ["homeassistant", None],
            "redirect_uri": redirect_uri,
            "type": "authorize"
        }
        try:
            session = async_get_clientsession(self._hass, verify_ssl=False)
            if not self._flow_id:
                with async_timeout.timeout(5, loop=self._hass.loop):
                    response = await session.post(self._ha_url+'/auth/login_flow', json=data)
                result = await response.json()
                self._flow_id = result.get('flow_id')
            if self._flow_id:
                data = {
                    "client_id": client_id,
                    'username': username,
                    'password': password
                }

                with async_timeout.timeout(5, loop=self._hass.loop):
                    response = await session.post(self._ha_url+'/auth/login_flow/'+self._flow_id, json=data)
                result = await response.json()
                code = result.get('result')
                if code:
                    self._flow_id = None
                    login_attemp['count'] = 0
                    login_attemp['first_time'] = None
                    data = {
                        'code': code
                    }
                    if state:
                        data.update({'state': state})
                    query_string = urlencode(data)
                    redirect_uri = parts.scheme + '://' + parts.netloc + parts.path +'?' + query_string + '&' + parts.query
                    _LOGGER.debug("[%s][auth] redirect_uri = %s", LOGGER_NAME, redirect_uri)
                    return self.json({ 'code': 'ok', 'Msg': '成功授权', 'data': {'location': redirect_uri}})
                    # return web.Response(headers={'Location': redirect_uri+'?'+query_string}, status=303)
                else:
                    if not login_attemp['first_time']:
                        login_attemp['first_time'] = datetime.now()
                    login_attemp['count'] += 1
                    login_attemp['last_time'] = datetime.now()
                    # location = request.headers.get('Referer')
                    # return web.Response(headers={'Location': location}, status=303)
            return self.json({ 'code': 'error', 'Msg': '用户密码错误/服务异常'})
        except(asyncio.TimeoutError, aiohttp.ClientError) as e:
            _LOGGER.error("[%s][auth] timeout", LOGGER_NAME)
            return self.json({ 'code': 'error', 'Msg': repr(e)})
        except Exception as e:
            _LOGGER.error("[%s][auth] %s", LOGGER_NAME, traceback.format_exc())
            return self.json({ 'code': 'error', 'Msg': repr(e)})

class HavcsTokenView(HomeAssistantView):
    """View to handle Configuration requests."""

    url = '/havcs/auth/token'
    name = 'havcs:auth:token'
    requires_auth = False

    def __init__(self, hass, ha_url, expiration):
        self._hass = hass
        self._havcs_token_url = ha_url + self.url
        self._token_url = ha_url + '/auth/token'
        self._client_id = ha_url
        self._expiration = expiration

    async def get(self, request):
        return web.Response(body='404 (￣ε￣) 访问到空气页面 (￣з￣)', status=404)

    async def post(self, request):
        headers = request.headers
        _LOGGER.debug("[%s][auth] request headers : %s", LOGGER_NAME, headers)
        body_data = await request.text()
        _LOGGER.debug("[%s][auth] request data : %s", LOGGER_NAME, body_data)
        try:
            data = json.loads(body_data)
        except json.decoder.JSONDecodeError:
            query_string = body_data if body_data else request.query_string
            _LOGGER.debug("[%s][auth] request query : %s", LOGGER_NAME, query_string)
            data = { k:v[0] for k, v in parse.parse_qs(query_string).items() }
        except:
            _LOGGER.error("[%s][auth] handle request : %s", LOGGER_NAME, traceback.format_exc() )

        # self._platform_uri = data.get('redirect_uri')
        # data['redirect_uri'] = self._havcs_token_url
        grant_type = data.get('grant_type')
        redirect_uri = data.get('redirect_uri')
        client_id = data.get('client_id')
        client_secret = data.get('client_secret')
        if not all((grant_type, redirect_uri, client_id, client_secret)):
            _LOGGER.error("[%s][auth] Invalid request: data = %s", LOGGER_NAME, data)
            web.Response(body='400 ?(￣△￣?) 参数不全拒绝访问 (?￣△￣)?', status=400)
        validation = False
        parts = urlparse(redirect_uri)
        if client_id.startswith('https://'):
            validation = True
        else:
            for platform in CLIENT_PALTFORM_DICT.keys():
                if client_id.startswith(platform) and parts.scheme + '://' + parts.netloc == CLIENT_PALTFORM_DICT[platform]:
                    validation = client_secret == self._hass.data[INTEGRATION][DATA_HAVCS_CONFIG].get('http', {}).get('clients', {}).get(client_id)
                    data['client_id'] = CLIENT_PALTFORM_DICT[platform]
        if not validation:
            _LOGGER.error("[%s][auth] Invalid client(client_id = %s, client_secret = %s): client_id or client_secret wrong", LOGGER_NAME, client_id, client_secret)
            web.Response(body='401 Σ( ° △ °|||) 验证失败拒绝访问', status=401)
        _LOGGER.debug("[%s][auth] forward request: data = %s", LOGGER_NAME, data)
        try:
            session = async_get_clientsession(self._hass, verify_ssl=False)
            with async_timeout.timeout(5, loop=self._hass.loop):
                response = await session.post(self._token_url, data=data)
        except(asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("[%s][auth] fail to get token, access %s in local network: timeout", LOGGER_NAME, self._token_url)
            return web.Response(status=500)
        except:
            _LOGGER.error("[%s][auth] fail to get token, access %s in local network: %s", LOGGER_NAME, self._token_url, traceback.format_exc())
            return web.Response(status=500)

        if grant_type == 'authorization_code':
            try:
                result = await response.json()
                result['expires_in'] = int(self._expiration.total_seconds())
                _LOGGER.debug("[%s][auth] get access token[%s] with default expiration, try to update expiration param and get new access token through another refresh token request.", LOGGER_NAME, result.get('access_token'))
                access_token = result.get('access_token')
                await havcs_util.async_update_token_expiration(access_token, self._hass, self._expiration)

                try:
                    refresh_token_data = {'client_id': data.get('client_id'), 'grant_type': 'refresh_token', 'refresh_token': result.get('refresh_token')}
                    session = async_get_clientsession(self._hass, verify_ssl=False)
                    with async_timeout.timeout(5, loop=self._hass.loop):
                        response = await session.post(self._token_url, data=refresh_token_data)
                except(asyncio.TimeoutError, aiohttp.ClientError):
                    _LOGGER.error("[%s][auth] fail to get new access token, access %s in local network: timeout", LOGGER_NAME, self._token_url)
                    return web.Response(status=response.status)
                
                try:
                    refresh_token_result = await response.json()
                    _LOGGER.debug("[%s][auth] get new access token[%s] with new expiration.", LOGGER_NAME, refresh_token_result.get('access_token'))
                    result['access_token'] = refresh_token_result.get('access_token')
                    _LOGGER.debug("[%s][auth] success to deal %s request, return access token.", LOGGER_NAME, grant_type)
                    return self.json(result)
                except:
                    result = await response.text()
                    _LOGGER.error("[%s][auth] fail to get new access token, access %s in local network, get response: status = %s, data = %s", LOGGER_NAME, self._token_url, response.status, result)
                    return web.Response(status=response.status)
            except:
                result = await response.text()
                _LOGGER.error("[%s][auth] %s", LOGGER_NAME, traceback.format_exc())
                _LOGGER.error("[%s][auth] fail to get token from %s in local network, get response: status = %s, data = %s", LOGGER_NAME, self._token_url, response.status, result)
                return web.Response(status=response.status)
        elif grant_type == 'refresh_token':
            try:
                result = await response.json()
                result['refresh_token'] = data.get('refresh_token')
                _LOGGER.debug("[%s][auth] deal %s request, return refresh_token again: status = %s, data = %s", LOGGER_NAME, grant_type, response.status, result)
                return self.json(result)
            except:
                result = await response.text()
                _LOGGER.error("[%s][auth] fail to deal %s request, get response: status = %s, data = %s", LOGGER_NAME, grant_type, response.status, result)
                return web.Response(status=response.status)
        else:
            try:
                result = await response.json()
                _LOGGER.debug("[%s][auth] success to deal %s request, get response: status = %s, data = %s", LOGGER_NAME, grant_type, response.status, result)
                return self.json(result)
            except:
                result = await response.text()
                _LOGGER.error("[%s][auth] fail to deal %s request, get response: status = %s, data = %s", LOGGER_NAME, grant_type, response.status, result)
                return web.Response(status=response.status)
        # return web.Response( headers={'Location': self._auth_url+'?'+query_string}, status=303)

class HavcsDeviceView(HomeAssistantView):
    url = '/havcs/device'
    name = 'havcs:device'
    requires_auth = True

    def __init__(self, hass, device_schema):
        self._hass = hass
        self._device_schema = device_schema
        local = hass.config.path("custom_components/" + INTEGRATION + "/html")
        if os.path.isdir(local):
            hass.http.register_static_path('/havcs', local, False)
        panels = hass.data.setdefault(DATA_PANELS, {})
        if INTEGRATION not in panels:
            hass.components.frontend.async_register_built_in_panel(
                component_name = "iframe",
                sidebar_title = 'HAVCS设备',
                sidebar_icon = 'mdi:home-edit',
                frontend_url_path = INTEGRATION,
                config = {"url": '/havcs/index.html'},
                require_admin = True
            )

    async def get(self, request):
        return web.Response(body='404 (￣ε￣) 访问到空气页面 (￣з￣)', status=404)

    async def post(self, request):
        if request.content_type == 'multipart/form-data':
            req = await request.post()
        else:
            req = await request.json()
        action = req.get('action')
        if action == 'getList':
            device_list = [ {**{'device_id': device_id}, **device_attributes} for device_id, device_attributes in self._hass.data[INTEGRATION][DATA_HAVCS_ITEMS].items()]
            return self.json({ 'code': 'ok', 'Msg': '成功获取设备清单', 'data': device_list})
        elif action == 'get':
            device_id = req.get('device_id')
            device = self._hass.data[INTEGRATION][DATA_HAVCS_ITEMS].get(device_id)
            if device:
                return self.json({ 'code': 'ok', 'Msg': '成功获取设备', 'data': {**{'device_id': device_id}, **device}})
        elif action == 'getDict':
            dict_names = req.get('data')
            data = {}
            for dict_name in dict_names:
                dict_data = globals().get('DEVICE_' + dict_name.upper() + '_DICT')
                if dict_data:
                    data.update({dict_name: dict_data})
                else:
                    return self.json({ 'code': 'error', 'Msg': '获取'+dict_name+'字典失败'})
            return self.json({ 'code': 'ok', 'Msg': '成功获取字典', 'data':data})
        elif action == 'delete':
            device_id = req.get('device_id')
            self._hass.data[INTEGRATION][DATA_HAVCS_ITEMS].pop(device_id)
            save_yaml(self._hass.data[INTEGRATION][CONF_DEVICE_CONFIG_PATH], self._hass.data[INTEGRATION][DATA_HAVCS_ITEMS])
            return self.json({ 'code': 'ok', 'Msg': '成功删除设备', 'data':{'device_id': device_id}})
        elif action == 'update':
            device = req.get('device')
            device_id = device.pop('device_id')
            if device_id:
                try:
                    valid_device = self._device_schema({device_id: device})
                    self._hass.data[INTEGRATION][DATA_HAVCS_ITEMS].setdefault(device_id, {})
                    self._hass.data[INTEGRATION][DATA_HAVCS_ITEMS][device_id].update(device)
                    save_yaml(self._hass.data[INTEGRATION][CONF_DEVICE_CONFIG_PATH], self._hass.data[INTEGRATION][DATA_HAVCS_ITEMS])
                    return self.json({ 'code': 'ok', 'Msg': '成功新增/更新设备', 'data':{'device_id': device_id}})
                except er.Invalid as e:
                    msg = '属性校验失败：' + e.msg + ' @ data'
                    for path in e.path:
                        msg += '[' + str(path) + ']'
                    _LOGGER.error("[%s][device] fail to import devices : %s", LOGGER_NAME, msg)
                    return self.json({ 'code': 'error', 'Msg': msg})
                except Exception as e:
                    _LOGGER.error("[%s][device] fail to update device (%s: %s) : %s", LOGGER_NAME, device_id, device, traceback.format_exc())
                    return self.json({ 'code': 'error', 'Msg': repr(e)})
        elif action == 'export': 
            response = web.FileResponse(os.path.join(self._hass.config.config_dir, 'havcs-ui.yaml'), headers={'Content-Disposition': 'havcs-ui.yaml'})
            response.enable_compression()
            return response
        elif action == 'import':
            upload_file = req.get('file')
            try:
                device_config = yaml.load(upload_file.file, Loader=loader.SafeLineLoader)
                self._hass.data[INTEGRATION][DATA_HAVCS_ITEMS] = self._device_schema(device_config)
                save_yaml(self._hass.data[INTEGRATION][CONF_DEVICE_CONFIG_PATH], self._hass.data[INTEGRATION][DATA_HAVCS_ITEMS])
                return self.json({ 'code': 'ok', 'Msg': '成功导入设备'})
            except er.Invalid as e:
                msg = '属性校验失败：' + e.msg + ' @ data'
                for path in e.path:
                    msg += '[' + str(path) + ']'
                _LOGGER.error("[%s][device] fail to import devices : %s", LOGGER_NAME, msg)
                return self.json({ 'code': 'error', 'Msg': msg})
            except Exception as e:
                _LOGGER.error("[%s][device] fail to import devices : %s", LOGGER_NAME, traceback.format_exc())
                return self.json({ 'code': 'error', 'Msg': repr(e)})
        elif action == 'sync':
            await self._hass.services.async_call('havcs', 'reload')
            return self.json({ 'code': 'ok', 'Msg': '成功同步设备'})
        elif action == 'config':
            return self.json({ 'code': 'ok', 'Msg': '成功获取配置信息', 'data': ['配置文件路径<br/>' + os.path.join(self._hass.config.config_dir, 'configuration.yaml'), self._hass.data[INTEGRATION][DATA_HAVCS_CONFIG]]})
        return self.json({ 'code': 'error', 'Msg': '请求 '+action+' 失败'})

class HavcsHttpManager:
    def __init__(self, hass, ha_url, device_schema):
        self._retry_remove = None
        self._retry_times = 3
        self._hass = hass
        self._ha_url = ha_url
        self._expiration = None
        self._device_schema = device_schema
    
    def set_expiration(self, expiration):
        self._expiration = expiration

    def register_service(self):
        self._hass.http.register_view(HavcsServiceView(self._hass))

    def register_auth_authorize(self):
        self._hass.http.register_view(HavcsAuthorizeView(self._hass, self._ha_url))

    def register_auth_token(self):
        self._hass.http.register_view(HavcsTokenView(self._hass, self._ha_url, self._expiration))

    def register_deivce_manager(self):
        self._hass.http.register_view(HavcsDeviceView(self._hass, self._device_schema))

    async def async_check_http_oauth(self, triggered=None):
        _LOGGER.debug("[%s] check accessibility from local", LOGGER_NAME)
        try:
            if self._retry_remove is not None:
                self._retry_remove()
                self._retry_remove = None

            session = async_get_clientsession(self._hass, verify_ssl=False)
            with async_timeout.timeout(5, loop= self._hass.loop):
                response = await session.get(self._ha_url + '/havcs/auth/authorize')
            if response.status == 401:
                _LOGGER.debug("[%s][check] access success: url = %s, status = %s", LOGGER_NAME, self._ha_url + '/havcs/auth/authorize', response.status)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.debug("[%s][check] retry check after 15s", LOGGER_NAME)
            self._retry_times -= 1
            if(self._retry_times > 0):
                self._retry_remove = async_track_time_interval(
                    self._hass, self.async_check_http_oauth, timedelta(seconds=15)
                )
            else:
                _LOGGER.error("[%s][check] can not access http, check `ha_url` in configuration.yml", LOGGER_NAME)
        except Exception:
            _LOGGER.exception("[%s][check] unexpected error occur", LOGGER_NAME)
            raise