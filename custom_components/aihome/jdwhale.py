import json, math, time
import logging
import uuid
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (MAJOR_VERSION, MINOR_VERSION)
from homeassistant.auth.const import ACCESS_TOKEN_EXPIRATION
import homeassistant.util.color as color_util
import homeassistant.auth.models as models
from typing import Optional
from datetime import timedelta
from homeassistant.helpers.state import AsyncTrackStates
from urllib.request import urlopen

from .util import (decrypt_device_id,encrypt_entity_id)
import copy

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)

AI_HOME = True
DOMAIN  = 'jdwhale'
REPORT_WHEN_STARUP = True

async def async_setup(hass, config):
    hass.http.register_view(JdWhaleGateVidw(hass))
    return True

class JdWhaleGateVidw(HomeAssistantView):
    """View to handle Configuration requests."""

    url = '/jdwhale_gate'
    name = 'jdwhale_gate'
    # requires_auth = True    # 使用request头验证token

    def __init__(self, hass):
        """Initialize the token view."""
        self._jdwhale = Jdwhale(hass,['http'])
        
    async def post(self, request):
        """Update state of entity."""
        try:
            data = await request.json()
            response = await self._jdwhale.handleRequest(data)
        except:
            import traceback
            _LOGGER.error(traceback.format_exc())
            response = {}

        return self.json(response)

def createHandler(hass):
    mode = ['handler']
    if REPORT_WHEN_STARUP:
        mode.append('report_when_starup')
    return Jdwhale(hass, mode)

class Jdwhale:
    def __init__(self, hass, mode):
        self._mode = mode
        self._hass = hass
        self._DEVICE_TYPES = {
            'WASHING_MACHINE': '洗衣机',
            'SWEEPING_ROBOT': '扫地机器人',
            'WATER_HEATER': '热水器',
            'AIR_CONDITION': '空调',
            'AIR_CLEANER': '空气净化器',
            'SWITCH': '开关',
            'LIGHT': '灯',
            'SOCKET': '插座',
            'FRIDGE': '冰箱',
            'FAN': '风扇',
            'MICROWAVE_OVEN': '微波炉',
            'TV_SET': '电视',
            'DISHWASHER': '洗碗机',
            'OVEN': '烤箱',
            'WATER_CLEANER': '净水器',
            'HUMIDIFIER': '加湿器',
            'SETTOP_BOX': '机顶盒',
            'HEATER': '电暖气',
            'INDUCTION_COOKER': '电饭煲',
            'CURTAIN': '窗帘',
            'RANGE_HOOD': '抽油烟机',
            'BREAD_MAKER': '面包机',
        }
        self._INCLUDE_DOMAINS = {
            'climate': 'AIR_CONDITION',
            'fan': 'FAN',
            'light': 'LIGHT',
            'media_player': 'TV_SET',
            'switch': 'SWITCH',
            'vacuum': 'SWEEPING_ROBOT',
            'sensor': 'sensor',
            'cover': 'CURTAIN'
        }
        self._EXCLUDE_DOMAINS = [
            'automation',
            'binary_sensor',
            'device_tracker',
            'group',
            'zone',
            'sun',
        ]
        self._ALL_ACTIONS = {
            'TurnOn': '打开%s',
            'TurnOff': '关闭%s',
            'AdjustUpBrightness': '调高%s亮度',
            'AdjustDownBrightness': '调低%s亮度',
            'SetBrightness': '设置%s亮度',
            'SetColor': '设置%s颜色',
            'AdjustUpTemperature': '调高%s温度',
            'AdjustDownTemperature': '调低%s温度',
            'SetTemperature': '设置%s温度',
            'AdjustUpWindSpeed': '调高%s风速',
            'AdjustDownWindSpeed': '调低%s风速',
            'SetWindSpeed': '设置%s风速',
            'AdjustUpVolume': '调高%s音量',
            'AdjustDownVolume': '调低%s音量',
            'SetVolume': '设置%s音量',
            'SetMute': '设置%s静音',
            'AdjustUpTVChannel': '调高%s频道数字',
            'AdjustDownTVChannel': '调低%s频道数字',
            'SetTVChannel': '设置%s频道',
            'ReturnTVChannel': '返回上一个频道',
            'Play': '播放',
            'Stop': '停止',
            'Next': '下一个',
            'Pause': '暂停',
            'Previous': '上一个',
            'SetMode': '设置%s模式',
            'Query': '查询%s的状态',
            'QueryPowerState': '查询%s的电源状态',
            'QueryColor': '查询%s的颜色',
            'QueryTemperature': '查询%s的温度',
            'QueryWindspeed': '查询%s的风速',
            'QueryBrightness': '查询%s的亮度',
            'QueryHumidity': '查询%s的湿度',
            'QueryPM25': '查询%s的PM2.5',
            'QueryMode': '查询%s的模式',
        }
        self._TRANSLATIONS = {
            'cover': {
                'TurnOnRequest':  'open_cover',
                'TurnOffRequest': 'close_cover',
            },
            'vacuum': {
                'TurnOnRequest':  'start',
                'TurnOffRequest': 'return_to_base',
                'SetSuctionRequest': lambda state, payload: ('fan', 'set_fan_speed', {'fan_speed': 90 if payload['suction']['value'] == 'STRONG' else 60}),
            },
            'switch': {
                'TurnOnRequest': 'turn_on',
                'TurnOffRequest': 'turn_off',
            },
            'light': {
                'TurnOnRequest':  'turn_on',
                'TurnOffRequest': 'turn_off',
                'SetBrightnessPercentageRequest': lambda state, payload: ('light', 'turn_on', {'brightness_pct': payload['brightness']['value']}),
                'IncrementBrightnessPercentageRequest': lambda state, payload: ('light', 'turn_on', {'brightness_pct': min(state.attributes['brightness'] / 255 * 100 + payload['deltaPercentage'][
                    'value'], 100)}),
                'DecrementBrightnessPercentageRequest': lambda state, payload: ('light', 'turn_on', {'brightness_pct': max(state.attributes['brightness'] / 255 * 100 - payload['deltaPercentage']['value'], 0)}),
                'SetColorRequest': lambda state, payload: ('light', 'turn_on', {"hs_color": [float(payload['color']['hue']), float(payload['color']['saturation']) * 100]})
            },
            'sensor':{
                'QueryTemperatureRequest'
            },
            'input_boolean':{
                'TurnOnRequest': lambda state, payload:(state.attributes['aihome_actions']['turn_on'][0], state.attributes['aihome_actions']['turn_on'][1], json.loads(state.attributes['aihome_actions']['turn_on'][2])) if state.attributes.get('aihome_actions') else ('input_boolean', 'turn_on', {}),
                'TurnOffRequest': lambda state, payload:(state.attributes['aihome_actions']['turn_off'][0], state.attributes['aihome_actions']['turn_off'][1], json.loads(state.attributes['aihome_actions']['turn_off'][2])) if state.attributes.get('aihome_actions') else ('input_boolean', 'turn_off', {}),
            }

        }
            
    def _errorResult(self, errorCode, messsage=None):
        """Generate error result"""
        messages = {
            'INVALIDATE_CONTROL_ORDER': 'invalidate control order',
            'SERVICE_ERROR': 'service error',
            'DEVICE_NOT_SUPPORT_FUNCTION': 'device not support',
            'INVALIDATE_PARAMS': 'invalidate params',
            'DEVICE_IS_NOT_EXIST': 'device is not exist',
            'IOT_DEVICE_OFFLINE': 'device is offline',
            'IOT_DEVICE_POWEROFF': 'device is poweroff',
            'ACCESS_TOKEN_INVALIDATE': 'access_token is invalidate',
            'PARAMS_OVERSTEP_MAX': 'params overstep max',
            'PARAMS_OVERSTEP_MIN': 'params overstep min'
        }
        return {'errorCode': errorCode, 'message': messsage if messsage else messages[errorCode]}

    async def handleRequest(self, data, ignoreToken = False):
        """Handle request"""
        # _LOGGER.info("Handle Request: %s", data)
        header = data['header']
        payload = data['payload']
        properties = None
        name = header['name']
        p_user_id = header.get('userId','')
        # uid = p_user_id+'@'+DOMAIN

        token = await self._hass.auth.async_validate_access_token(payload['accessToken'])
        if ignoreToken or token is not None:
            namespace = header['namespace']
            if namespace == 'Alpha.Iot.Device.Discover':
                discovery_devices,entity_ids = self._discoveryDevice()
                result = {'deviceInfo': discovery_devices}
                await self._hass.data['aihome_bind_manager'].async_save_changed_devices(entity_ids, DOMAIN, p_user_id)
            elif namespace == 'Alpha.Iot.Device.Control':
                result = await self._controlDevice(name, payload)
            elif namespace == 'Alpha.Iot.Device.Query':
                result = self._queryDevice(name, payload)
                if not 'errorCode' in result:
                    result = {'deviceId': payload['deviceId'], 'properties': result}
            else:
                result = self._errorResult('SERVICE_ERROR')
        else:
            result = self._errorResult('ACCESS_TOKEN_INVALIDATE')

        # Check error and fill response name
        if 'errorCode' in result:
            header['name'] = 'ErrorResponse'
            if 'deviceId' in payload:
                result['deviceId'] = payload['deviceId']
        else:
            header['name'] = name.replace('Request','Response')
    
        response = {'header': header, 'payload': result}

        _LOGGER.info("Respnose: %s", response)
        return response
  
    def _discoveryDevice(self):

        states = self._hass.states.async_all()
        # groups_ttributes = groupsAttributes(states)

        devices = []
        entity_ids = []

        for state in states:
            attributes = state.attributes
            # _LOGGER.debug('-----entity_id: %s, aihome_device: %s', state.entity_id, attributes.get('aihome_device'))
            if not attributes.get('aihome_device', False):
                continue

            friendly_name = attributes.get('friendly_name')
            if friendly_name is None:
                continue

            entity_id = state.entity_id
            # _LOGGER.debug('-----entity_id: %s, attributes: %s', entity_id, attributes)
            deviceType = self._guessDeviceType(entity_id, attributes)
            if deviceType is None:
                continue

            properties,actions = self._guessPropertyAndAction(entity_id, attributes, state.state)
            # if properties is None:
            #     continue
            if deviceType == 'sensor':
                if attributes.get('aihome_sensor_group') is None:
                    continue
                # _LOGGER.debug('-----entity_id: %s, attributes: %s', entity_id, attributes)

                sensor_ids = self._hass.states.get(attributes.get('aihome_sensor_group')).attributes.get('entity_id')
                for sensor in sensor_ids:
                    if sensor.startswith('sensor.'):
                        prop,action = self._guessPropertyAndAction(sensor, self._hass.states.get(sensor).attributes, self._hass.states.get(sensor).state)
                        actions += action
                actions = list(set(actions))
                deviceType = 'AIR_CLEANER'

            devices.append({
                'actions': actions,
                'controlSpeech': [self._ALL_ACTIONS.get(action,'')%(friendly_name) for action in actions ],
                'deviceId': encrypt_entity_id(entity_id),
                'deviceTypes': deviceType,
                'extensions': {'manufacturerName': 'HomeAssistant'},
                'friendlyDescription': friendly_name,
                'friendlyName': friendly_name,
                'isReachable': '1',
                'modelName': 'HomeAssistantDevice',
                })
            entity_ids.append(entity_id)
        
        return devices, entity_ids

    async def _controlDevice(self, cmnd, payload):
        entity_id = decrypt_device_id(payload['deviceId'])
        domain = entity_id[:entity_id.find('.')]
        data = {"entity_id": entity_id }
        if domain in self._TRANSLATIONS.keys():
            translation = self._TRANSLATIONS[domain][cmnd]
            if callable(translation):
                domain, service, content = translation(self._hass.states.get(entity_id), payload)
                data.update(content)
            else:
                service = translation
        else:
            service = self._getControlService(cmnd)

        _LOGGER.info(self._hass.states.get(entity_id).attributes)
        with AsyncTrackStates(self._hass) as changed_states:
            result = await self._hass.services.async_call(domain, service, data, True)

        return {"result": "SUCCESS"} if result else self._errorResult('IOT_DEVICE_OFFLINE')


    def _queryDevice(self, cmnd, payload):
        entity_id = decrypt_device_id(payload['deviceId'])
        state = self._hass.states.get(entity_id)

        if entity_id.startswith('sensor.'):
            entity_ids = self._hass.states.get(state.attributes.get('aihome_sensor_group')).attributes.get('entity_id')

            # properties = [{'name':'PowerState', 'value':'on'}]
            properties = []
            for entity_id in entity_ids:
                entity = self._hass.states.get(entity_id)
                if entity_id.startswith('sensor.') and entity.attributes.get('aihome_sensor') is not None :
                    prop,action = self._guessPropertyAndAction(entity_id, entity.attributes, entity.state)
                    _LOGGER.debug('property:%s', prop)
                    if prop is None:
                        continue
                    elif prop.get('name').lower() in cmnd.lower():
                        properties = prop #单一状态直接返回，不适用数组
                        break
                    elif cmnd == 'QueryRequest':
                        properties.append(prop)
            return properties if properties else self._errorResult('IOT_DEVICE_OFFLINE')
        else:
            if state is not None and state.state != 'unavailable':
                return {'name':'PowerState', 'value':state.state} if cmnd != 'QueryRequest' else [{'name':'PowerState', 'value':state.state}]
        return self._errorResult('IOT_DEVICE_OFFLINE')

    def _getControlService(self, action):
        i = 0
        service = ''
        for c in action.split('Request')[0]:
            service += (('_' if i else '') + c.lower()) if c.isupper() else c
            i += 1
        return service 

    def _guessDeviceType(self, entity_id, attributes):
        if 'jdwhale_deviceType' in attributes:
            return attributes['jdwhale_deviceType']

        # Exclude with domain
        domain = entity_id[:entity_id.find('.')]
        if domain in self._EXCLUDE_DOMAINS:
            return None

        # Guess from entity_id
        for deviceType in self._DEVICE_TYPES.keys():
            if deviceType in entity_id:
                return deviceType

        # Map from domain
        if domain in self._INCLUDE_DOMAINS:
            return self._INCLUDE_DOMAINS[domain]

        return None


    def _groupsAttributes(self, states):
        groups_attributes = []
        for state in states:
            group_entity_id = state.entity_id
            if group_entity_id.startswith('group.') and not group_entity_id.startswith('group.all_') and group_entity_id != 'group.default_view':
                group_attributes = state.attributes
                if 'entity_id' in group_attributes:
                    groups_attributes.append(group_attributes)
        return groups_attributes


    def _guessPropertyAndAction(self, entity_id, attributes = None, state = None):
        # Support On/Off/Query only at this time
        if 'jdwhale_actions' in attributes:
            actions = copy.deepcopy(attributes['jdwhale_actions']) # fix
        elif entity_id.startswith('switch.'):
            actions = ["TurnOn", "TurnOff"]
        elif entity_id.startswith('light.'):
            actions = ["TurnOn", "TurnOff", "SetBrightness", "AdjustUpBrightness", "AdjustDownBrightness", "setColor"]
        elif entity_id.startswith('cover.'):
            actions = ["TurnOn", "TurnOff", "Pause"]
        elif entity_id.startswith('vacuum.'):
            actions = ["TurnOn", "TurnOff"]
        elif entity_id.startswith('sensor.'):
            actions = ["Query", "QueryTemperature", "QueryHumidity"]
        else:
            actions = ["TurnOn", "TurnOff"]

        if 'jdwhale_property' in attributes:
            name = attributes['jdwhale_property']
        elif entity_id.startswith('sensor.'):
            unit = attributes['unit_of_measurement'] if 'unit_of_measurement' in attributes else ''
            if unit == u'°C' or unit == u'℃':
                name = 'Temperature'
            elif unit == 'lx' or unit == 'lm':
                name = 'Brightness'
            elif ('hcho' in entity_id):
                name = 'Fog'
            elif ('humidity' in entity_id):
                name = 'Humidity'
            elif ('pm25' in entity_id):
                name = 'PM25'
            elif ('co2' in entity_id):
                name = 'WindSpeed'
            else:
                name = None
        else:
            name = 'PowerState'
            if state != 'off':
                state = 'on'
        properties = {'name': name, 'value': state} if name is not None else None
        return properties, actions

    @property
    def should_report_when_starup(self):
        return True if 'report_when_starup' in self._mode else False

    async def bind_device(self,p_user_id, bind_entity_ids, unbind_entity_ids, devices):
        payload = []
        for device in devices:
            entity_id = decrypt_device_id(device['deviceId'])
            if entity_id in bind_entity_ids:
                bind_payload  ={
                    "header": {
                        "namespace": "Alpha.Iot.Device.Report",
                        "name": "BindDeviceEvent",
                        "messageId": str(uuid.uuid4()),
                        "payLoadVersion": "1"
                        },
                    "payload": {
                        "skillId": "",
                        "userId": p_user_id,
                        "deviceInfo": device
                    }
                }
                payload.append(bind_payload)
        for entity_id in unbind_entity_ids:
            unbind_payload ={
                "header": {
                    "namespace": "Alpha.Iot.Device.Report",
                    "name": "UnBindDeviceEvent",
                    "messageId": str(uuid.uuid4()),
                    "payLoadVersion": "1"
                },
                "payload": {
                    "skillId": "",
                    "userId": p_user_id,
                    "deviceId":encrypt_entity_id(entity_id)
                }
            }
            payload.append(unbind_payload)
        return payload    
    

