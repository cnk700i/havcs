import json
import logging
import uuid
import copy
import time
from urllib.request import urlopen
from .util import decrypt_device_id, encrypt_entity_id
from .helper import VoiceControlProcessor, VoiceControlDeviceManager

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)
LOGGER_NAME = 'aligenie'

AI_HOME = True
DOMAIN = 'aligenie'

def createHandler(hass):
    mode = ['handler']
    return VoiceControlAligenie(hass, mode)

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
        'query_color': 'QueryColor',
        'query_power_state': 'QueryPowerState',
        'query_temperature': 'QueryTemperature',
        'query_humidity': 'QueryHumidity',
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
        'watercooler': '饮水机',
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
    }

    device_type_map_h2p = {
        'climate': 'aircondition',
        'fan': 'fan',
        'light': 'light',
        'television': 'television',
        'media_player': 'television',
        'remote': 'telecontroller',
        'switch': 'switch',
        'sensor': 'sensor',
        'cover': 'curtain',
        'vacuum': 'roboticvacuum',
        }

    _service_map_p2h = {
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
        'input_boolean':{
            'TurnOn': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes['havcs_actions']['turn_on']], [cmnd[1] for cmnd in attributes['havcs_actions']['turn_on']], [json.loads(cmnd[2]) for cmnd in attributes['havcs_actions']['turn_on']]) if attributes.get('havcs_actions') else (['input_boolean'], ['turn_on'], [{}]),
            'TurnOff': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes['havcs_actions']['turn_off']], [cmnd[1] for cmnd in attributes['havcs_actions']['turn_off']], [json.loads(cmnd[2]) for cmnd in attributes['havcs_actions']['turn_off']]) if attributes.get('havcs_actions') else (['input_boolean'], ['turn_off'], [{}]),
            'AdjustUpBrightness': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes['havcs_actions']['increase_brightness']], [cmnd[1] for cmnd in attributes['havcs_actions']['increase_brightness']], [json.loads(cmnd[2]) for cmnd in attributes['havcs_actions']['increase_brightness']]) if attributes.get('havcs_actions') else (['input_boolean'], ['turn_on'], [{}]),
            'AdjustDownBrightness': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes['havcs_actions']['decrease_brightness']], [cmnd[1] for cmnd in attributes['havcs_actions']['decrease_brightness']], [json.loads(cmnd[2]) for cmnd in attributes['havcs_actions']['decrease_brightness']]) if attributes.get('havcs_actions') else (['input_boolean'], ['turn_on'], [{}]),
        }

    }
    # action:[{Platfrom Attr: HA Attr},{}]
    _query_map_p2h = {

    }

class VoiceControlAligenie(PlatformParameter, VoiceControlProcessor):
    def __init__(self, hass, mode):
        self._hass = hass
        self._mode = mode
        try:
            self._zone_constraints  = json.loads(urlopen('https://open.bot.tmall.com/oauth/api/placelist').read().decode('utf-8'))['data']
            self._device_name_constraints = json.loads(urlopen('https://open.bot.tmall.com/oauth/api/aliaslist').read().decode('utf-8'))['data']
            self._device_name_constraints.append({'key': '电视', 'value': ['电视机']})
            self._device_name_constraints.append({'key': '传感器', 'value': ['传感器']})
        except:
            self._zone_constraints = []
            self._device_name_constraints = []
            import traceback
            _LOGGER.info("[%s] can get places and aliases data from website, set None.\n%s", LOGGER_NAME, traceback.format_exc())
        self.vcdm = VoiceControlDeviceManager(DOMAIN, self.device_action_map_h2p, self.device_attribute_map_h2p, self._service_map_p2h, self.device_type_map_h2p, self._device_type_alias, self._device_name_constraints, self._zone_constraints)

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

    async def handleRequest(self, data, auth = False):
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
                err_result, discovery_devices, entity_ids = self.process_discovery_command()
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
            if name and state:
                properties += [{'name': name.lower(), 'value': state.state}]
        # return properties if properties else [{'name': 'powerstate', 'value': 'off'}]
        return properties
    
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
        return raw_device_type

    def _discovery_process_device_info(self, entity_id,  device_type, device_name, zone, properties, actions):
        return {
            'deviceId': encrypt_entity_id(entity_id),
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