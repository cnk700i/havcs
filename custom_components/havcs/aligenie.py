import json
from urllib.request import urlopen
import logging

import async_timeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .util import decrypt_device_id, encrypt_device_id
from .helper import VoiceControlProcessor, VoiceControlDeviceManager
from .const import ATTR_DEVICE_ACTIONS

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)
LOGGER_NAME = 'aligenie'

DOMAIN = 'aligenie'

async def createHandler(hass, entry):
    mode = ['handler']
    try:
        placelist_url = 'https://open.bot.tmall.com/oauth/api/placelist'
        aliaslist_url = 'https://open.bot.tmall.com/oauth/api/aliaslist'
        session = async_get_clientsession(hass, verify_ssl=False)
        with async_timeout.timeout(5, loop=hass.loop):
            response = await session.get(placelist_url)
        placelist  = (await response.json())['data']
        with async_timeout.timeout(5, loop=hass.loop):
            response = await session.get(aliaslist_url)
        aliaslist = (await response.json())['data']
        placelist.append({'key': '电视', 'value': ['电视机']})
        aliaslist.append({'key': '传感器', 'value': ['传感器']})
    except:
        placelist = []
        aliaslist = []
        import traceback
        _LOGGER.info("[%s] can get places and aliases data from website, set None.\n%s", LOGGER_NAME, traceback.format_exc())
    return VoiceControlAligenie(hass, mode, entry, placelist, aliaslist)

class PlatformParameter:
    device_attribute_map_h2p = {
        'power_state': 'powerstate',
        'color': 'color',
        'temperature': 'temperature',
        'humidity': 'humidity',
        # '': 'windspeed',
        'brightness': 'brightness',
        # '': 'direction',
        # '': 'angle',
        'pm25': 'pm2.5',
    }
    device_action_map_h2p ={
        'turn_on': 'TurnOn',
        'turn_off': 'TurnOff',
        'increase_brightness': 'AdjustUpBrightness',
        'decrease_brightness': 'AdjustDownBrightness',
        'set_brightness': 'SetBrightness',
        'increase_temperature': 'AdjustUpTemperature',
        'decrease_temperature': 'AdjustDownTemperature',
        'set_temperature': 'SetTemperature',
        'set_color': 'SetColor',
        'pause': 'Pause',
        'continue': 'Continue',
        'play': 'Play',
        'query_color': 'QueryColor',
        'query_power_state': 'QueryPowerState',
        'query_temperature': 'QueryTemperature',
        'query_humidity': 'QueryHumidity',
        'set_mode': 'SetMode'
        # '': 'QueryWindSpeed',
        # '': 'QueryBrightness',
        # '': 'QueryFog',
        # '': 'QueryMode',
        # '': 'QueryPM25',
        # '': 'QueryDirection',
        # '': 'QueryAngle'
    }
    _device_type_alias = {
        'television': '电视',
        'light': '灯',
        'aircondition': '空调',
        'airpurifier': '空气净化器',
        'outlet': '插座',
        'switch': '开关',
        'roboticvacuum': '扫地机器人',
        'curtain': '窗帘',
        'humidifier': '加湿器',
        'fan': '风扇',
        'bottlewarmer': '暖奶器',
        'soymilkmaker': '豆浆机',
        'kettle': '电热水壶',
        'waterdispenser': '饮水机',
        'camera': '摄像头',
        'router': '路由器',
        'cooker': '电饭煲',
        'waterheater': '热水器',
        'oven': '烤箱',
        'waterpurifier': '净水器',
        'fridge': '冰箱',
        'STB': '机顶盒',
        'sensor': '传感器',
        'washmachine': '洗衣机',
        'smartbed': '智能床',
        'aromamachine': '香薰机',
        'window': '窗',
        'kitchenventilator': '抽油烟机',
        'fingerprintlock': '指纹锁',
        'telecontroller': '万能遥控器',
        'dishwasher': '洗碗机',
        'dehumidifier': '除湿机',
        'dryer': '干衣机',
        'wall-hung-boiler': '壁挂炉',
        'microwaveoven': '微波炉',
        'heater': '取暖器',
        'mosquitoDispeller': '驱蚊器',
        'treadmill': '跑步机',
        'smart-gating': '智能门控',
        'smart-band': '智能手环',
        'hanger': '晾衣架',
        'bloodPressureMeter': '血压仪',
        'bloodGlucoseMeter': '血糖仪',
    }

    device_type_map_h2p = {
        'climate': 'aircondition',
        'fan': 'fan',
        'light': 'light',
        'media_player': 'television',
        'remote': 'telecontroller',
        'switch': 'switch',
        'sensor': 'sensor',
        'cover': 'curtain',
        'vacuum': 'roboticvacuum',
        }

    _service_map_p2h = {
        # 测试，暂无找到播放指定音乐话术，继续播放指令都是Play
        # 'media_player': {
        #     'Play': lambda state, attributes, payload: (['play_media'], ['play_media'], [{"media_content_id": payload['value'], "media_content_type": "playlist"}]),
        #     'Pause': 'media_pause',
        #     'Continue': 'media_play'
        # },
        # 模式和平台设备类型有关，自动模式 静音模式 睡眠风模式（fan类型） 睡眠模式（airpurifier类型）
        'fan': {
            'SetMode': lambda state, attributes, payload: (['fan'], ['set_speed'], [{"speed": payload['value']}])
        },
        'cover': {
            'TurnOn':  'open_cover',
            'TurnOff': 'close_cover',
            'Pause': 'stop_cover',
        },
        'vacuum': {
            'TurnOn':  'start',
            'TurnOff': 'return_to_base',
        },
        'light': {
            'TurnOn':  'turn_on',
            'TurnOff': 'turn_off',
            'SetBrightness':        lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': payload['value']}]),
            'AdjustUpBrightness':   lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': min(attributes['brightness_pct'] + payload['value'], 100)}]),
            'AdjustDownBrightness': lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': max(attributes['brightness_pct'] - payload['value'], 0)}]),
            'SetColor':             lambda state, attributes, payload: (['light'], ['turn_on'], [{"color_name": payload['value']}])
        },
        'havcs':{
            'TurnOn': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_on']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_on']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_on']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_on'], [{}]),
            'TurnOff': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_off']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_off']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_off']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_off'], [{}]),
            'AdjustUpBrightness': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['increase_brightness']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['increase_brightness']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['increase_brightness']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_on'], [{}]),
            'AdjustDownBrightness': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['decrease_brightness']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['decrease_brightness']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['decrease_brightness']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_on'], [{}]),
        }

    }
    # action:[{Platfrom Attr: HA Attr},{}]
    _query_map_p2h = {

    }

class VoiceControlAligenie(PlatformParameter, VoiceControlProcessor):
    def __init__(self, hass, mode, entry, zone_constraints, device_name_constraints):
        self._hass = hass
        self._mode = mode
        self._zone_constraints = zone_constraints
        self._device_name_constraints = device_name_constraints
        # try:
        #     self._zone_constraints  = json.loads(urlopen('https://open.bot.tmall.com/oauth/api/placelist').read().decode('utf-8'))['data']
        #     self._device_name_constraints = json.loads(urlopen('https://open.bot.tmall.com/oauth/api/aliaslist').read().decode('utf-8'))['data']
        #     self._device_name_constraints.append({'key': '电视', 'value': ['电视机']})
        #     self._device_name_constraints.append({'key': '传感器', 'value': ['传感器']})
        # except:
        #     self._zone_constraints = []
        #     self._device_name_constraints = []
        #     import traceback
        #     _LOGGER.info("[%s] can get places and aliases data from website, set None.\n%s", LOGGER_NAME, traceback.format_exc())
        self.vcdm = VoiceControlDeviceManager(entry, DOMAIN, self.device_action_map_h2p, self.device_attribute_map_h2p, self._service_map_p2h, self.device_type_map_h2p, self._device_type_alias, self._device_name_constraints, self._zone_constraints)

    def _errorResult(self, errorCode, messsage=None):
        """Generate error result"""
        messages = {
            'INVALIDATE_CONTROL_ORDER': 'invalidate control order',
            'SERVICE_ERROR': 'service error',
            'DEVICE_NOT_SUPPORT_FUNCTION': 'device not support',
            'INVALIDATE_PARAMS': 'invalidate params',
            'DEVICE_IS_NOT_EXIST': 'device is not exist',
            'IOT_DEVICE_OFFLINE': 'device is offline',
            'ACCESS_TOKEN_INVALIDATE': ' access_token is invalidate'
        }
        return {'errorCode': errorCode, 'message': messsage if messsage else messages[errorCode]}

    async def handleRequest(self, data, auth = False, request_from = "http"):
        """Handle request"""
        _LOGGER.info("[%s] Handle Request:\n%s", LOGGER_NAME, data)

        header = self._prase_command(data, 'header')
        payload = self._prase_command(data, 'payload')
        action = self._prase_command(data, 'action')
        namespace = self._prase_command(data, 'namespace')
        properties = None
        content = {}

        if auth:
            if namespace == 'AliGenie.Iot.Device.Discovery':
                err_result, discovery_devices, entity_ids = self.process_discovery_command(request_from)
                content = {'devices': discovery_devices}
            elif namespace == 'AliGenie.Iot.Device.Control':
                err_result, content = await self.process_control_command(data)
            elif namespace == 'AliGenie.Iot.Device.Query':
                err_result, content = self.process_query_command(data)
                if not err_result:
                    properties = content
                    content = {}
            else:
                err_result = self._errorResult('SERVICE_ERROR')
        else:
            err_result = self._errorResult('ACCESS_TOKEN_INVALIDATE')

        # Check error and fill response name
        if err_result:
            header['name'] = 'ErrorResponse'
            content = err_result
        else:
            header['name'] = action + 'Response'

        # Fill response deviceId
        if 'deviceId' in payload:
            content['deviceId'] = payload['deviceId']

        response = {'header': header, 'payload': content}
        if properties:
            response['properties'] = properties
        _LOGGER.info("[%s] Respnose:\n%s", LOGGER_NAME, response)
        return response

    def _prase_command(self, command, arg):
        header = command['header']
        payload = command['payload']

        if arg == 'device_id':
            return payload['deviceId']
        elif arg == 'action':
            return header['name']
        elif arg == 'user_uid':
            return payload.get('openUid','')
        elif arg == 'namespace':
            return header['namespace']
        else:
            return command.get(arg)

    def _discovery_process_propertites(self, device_properties):
        properties = []
        for device_property in device_properties:
            name = self.device_attribute_map_h2p.get(device_property.get('attribute'))
            state = self._hass.states.get(device_property.get('entity_id'))
            if name:
                value = state.state if state else 'unavailable'
                properties += [{'name': name.lower(), 'value': value}]
        return properties if properties else [{'name': 'powerstate', 'value': 'off'}]
    
    def _discovery_process_actions(self, device_properties, raw_actions):
        actions = []
        for device_property in device_properties:
            name = self.device_attribute_map_h2p.get(device_property.get('attribute'))
            if name:
                action = self.device_action_map_h2p.get('query_'+name)
                if action:
                    actions += [action,]
        for raw_action in raw_actions:
            action = self.device_action_map_h2p.get(raw_action)
            if action:
                actions += [action,]
        return list(set(actions))

    def _discovery_process_device_type(self, raw_device_type):
        # raw_device_type guess from device_id's domain transfer to platform style
        return raw_device_type if raw_device_type in self._device_type_alias else self.device_type_map_h2p.get(raw_device_type)

    def _discovery_process_device_info(self, device_id,  device_type, device_name, zone, properties, actions):
        return {
            'deviceId': encrypt_device_id(device_id),
            'deviceName': device_name,
            'deviceType': device_type,
            'zone': zone,
            'model': device_name,
            'brand': 'HomeAssistant',
            'icon': 'https://d33wubrfki0l68.cloudfront.net/cbf939aa9147fbe89f0a8db2707b5ffea6c192cf/c7c55/images/favicon-192x192-full.png',
            'properties': properties,
            'actions': actions
            #'extensions':{'extension1':'','extension2':''}
        }


    def _control_process_propertites(self, device_properties, action) -> None:
        return {}

    def _query_process_propertites(self, device_properties, action) -> None:
        properties = []
        action = action.replace('Request', '').replace('Get', '')
        if action in self._query_map_p2h:
            for property_name, attr_template in self._query_map_p2h[action].items():
                formattd_property = self.vcdm.format_property(self._hass, device_properties, attr_template)
                properties.append({property_name:formattd_property})
        else:
            for device_property in device_properties:
                state = self._hass.states.get(device_property.get('entity_id'))
                value = state.attributes.get(device_property.get('attribute'), state.state) if state else None
                if value:
                    if action == 'Query':
                        formattd_property = {'name': self.device_attribute_map_h2p.get(device_property.get('attribute')), 'value': value}
                        properties.append(formattd_property)
                    elif device_property.get('attribute') in action.lower():
                        formattd_property = {'name': self.device_attribute_map_h2p.get(device_property.get('attribute')), 'value': value}
                        properties = [formattd_property]
                        break
        return properties

    def _decrypt_device_id(self, device_id) -> None:
        return decrypt_device_id(device_id)