import json
import logging
import uuid
import copy
import time

from .util import decrypt_device_id, encrypt_device_id
from .helper import VoiceControlProcessor, VoiceControlDeviceManager
from .const import DEVICE_ATTRIBUTE_DICT, ATTR_DEVICE_ACTIONS, INTEGRATION, DATA_HAVCS_BIND_MANAGER

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)

DOMAIN = 'weixin'
LOGGER_NAME = 'weixin'

def createHandler(hass, enrty):
    mode = ['handler']
    return VoiceControlWeixin(hass, mode, enrty)

class PlatformParameter:
    device_attribute_map_h2p = {
        'temperature': 'temperature',
        'brightness': 'brightness',
        'humidity': 'humidity',
        'pm25': 'pm2.5',
        'co2': 'co2',
        'power_state': 'power_state'
    }
    device_action_map_h2p ={
        'turn_on': 'turn_on',
        'turn_off': 'turn_off',
        'timing_turn_on': 'timing_turn_on',
        'timing_turn_off': 'timing_turn_off',
        'increase_brightness': 'increase_brightness',
        'decrease_brightness': 'decrease_brightness',
        'set_brightness': 'set_brightness',
        # 'increase_temperature': 'incrementTemperature',
        # 'decrease_temperature': 'decrementTemperature',
        # 'set_temperature': 'setTemperature',
        'set_color': 'set_color',
        'pause': 'pause',
        # 'query_color': 'QueryColor',
        # 'query_power_state': 'getTurnOnState',
        'query_temperature': 'query_temperature',
        'query_humidity': 'query_humidity',
        # '': 'QueryWindSpeed',
        # '': 'QueryBrightness',
        # '': 'QueryFog',
        # '': 'QueryMode',
        # '': 'QueryPM25',
        # '': 'QueryDirection',
        # '': 'QueryAngle'
    }
    _device_type_alias = {
        'LIGHT': '灯',
        'FAN': '风扇',
        'SWITCH': '开关',
        'COVER': '窗帘',
        'CLIMATE': '空调',
        'SENSOR': '传感器',
        'VACUUM': '扫地机器人',
    }

    device_type_map_h2p = {
        'climate': 'CLIMATE',
        'fan': 'FAN',
        'light': 'LIGHT',
        'media_player': 'MEDIA_PLAYER',
        'switch': 'SWITCH',
        'sensor': 'SENSOR',
        'cover': 'COVER',
        'vacuum': 'VACUUM',
        }

    _service_map_p2h = {
        'cover': {
            'turn_on':  'open_cover',
            'turn_off': 'close_cover',
            'timing_turn_on': 'open_cover',
            'timing_turn_off': 'close_cover',
            'pause': 'stop_cover',
        },
        'vacuum': {
            'turn_on':  'start',
            'turn_off': 'return_to_base',
            'timing_turn_on': 'start',
            'timing_turn_off': 'return_to_base',
            'set_suction': lambda state, attributes, payload: (['vacuum'], ['set_fan_speed'], [{'fan_speed': 90 if payload['suction']['value'] == 'STRONG' else 60}]),
        },
        'switch': {
            'turn_on': 'turn_on',
            'turn_off': 'turn_off',
            'timing_turn_on': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'on', 'duration': int(payload['timestamp']['value']) - int(time.time())}]),
            'timing_turn_off': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'off', 'duration': int(payload['timestamp']['value']) - int(time.time())}])
        },
        'light': {
            'turn_on': 'turn_on',
            'turn_off': 'turn_off',
            'timing_turn_on': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'on', 'duration': int(payload['timestamp']['value']) - int(time.time())}]),
            'timing_turn_off': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'off', 'duration': int(payload['timestamp']['value']) - int(time.time())}]),
            'set_brightness': lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': payload['brightness']['value']}]),
            'increase_brightness': lambda state, attributes, payload: (['light'], ['turn_on'],[ {'brightness_pct': min(state.attributes['brightness'] / 255 * 100 + payload['deltaPercentage']['value'], 100)}]),
            'decrease_brightness': lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': max(state.attributes['brightness'] / 255 * 100 - payload['deltaPercentage']['value'], 0)}]),
            'SetColorRequest': lambda state, attributes, payload: (['light'], ['turn_on'], [{'hs_color': [float(payload['color']['hue']), float(payload['color']['saturation']) * 100], 'brightness_pct': float(payload['color']['brightness']) * 100}])
        },
        'havcs':{
            'turn_on': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_on']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_on']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_on']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_on'], [{}]),
            'turn_off': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_off']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_off']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_off']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_off'], [{}]),
            'increase_brightness': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['increase_brightness']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['increase_brightness']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['increase_brightness']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_on'], [{}]),
            'decrease_brightness': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['decrease_brightness']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['decrease_brightness']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['decrease_brightness']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_on'], [{}]),                 
            'timing_turn_on': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'custom:havcs_actions/timing_turn_on', 'duration': int(payload['timestamp']['value']) - int(time.time())}]),
            'timing_turn_off': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'custom:havcs_actions/timing_turn_off', 'duration': int(payload['timestamp']['value']) - int(time.time())}]),
        }

    }

    _query_map_p2h = {
        'query_temperature': {
            'temperature': {'value':'%temperature', 'scale': "°C"}
        }
    }

class VoiceControlWeixin(PlatformParameter, VoiceControlProcessor):
    def __init__(self, hass, mode, enrty):
        self._hass = hass
        self._mode = mode
        self.vcdm = VoiceControlDeviceManager(enrty, DOMAIN, self.device_action_map_h2p, self.device_attribute_map_h2p, self._service_map_p2h, self.device_type_map_h2p, self._device_type_alias)
    def _errorResult(self, errorCode, messsage=None):
        """Generate error result"""
        messages = {
            'INVALIDATE_CONTROL_ORDER': 'invalidate control order',
            'SERVICE_ERROR': 'service error',
            'DEVICE_NOT_SUPPORT_FUNCTION': 'device not support',
            'INVALIDATE_PARAMS': 'invalidate params',
            'DEVICE_IS_NOT_EXIST': 'device is not exist',
            'IOT_DEVICE_OFFLINE': 'device is offline',
            'ACCESS_TOKEN_INVALIDATE': 'access_token is invalidate'
        }
        return {'errorCode': errorCode, 'message': messsage if messsage else messages[errorCode]}

    async def handleRequest(self, data, auth = False):
        """Handle request"""
        _LOGGER.info("[%s] Handle Request:\n%s", LOGGER_NAME, data)

        header = self._prase_command(data, 'header')
        # action = self._prase_command(data, 'action')
        namespace = self._prase_command(data, 'namespace')
        p_user_id = self._prase_command(data, 'user_uid')
        result = {}
        # uid = p_user_id+'@'+DOMAIN

        if auth:
            namespace = header['namespace']
            if 'Discoverer' in namespace:
                err_result, discovery_devices, entity_ids = self.process_discovery_command()
                result = {'discoveredDevices': discovery_devices}
                await self._hass.data[INTEGRATION][DATA_HAVCS_BIND_MANAGER].async_save_changed_devices(entity_ids, DOMAIN, p_user_id)
            elif 'Controller' in namespace:
                err_result, properties = await self.process_control_command(data)
                result = err_result if err_result else {'properties': properties}
            elif 'Reporter' in namespace:
                err_result, properties = self.process_query_command(data)
                result = err_result if err_result else {'properties': properties}
            else:
                result = self._errorResult('SERVICE_ERROR')
        else:
            result = self._errorResult('ACCESS_TOKEN_INVALIDATE')
        
        # Check error
        header['name'] = 'Response'
        if 'errorCode' in result:
            header['name'] = 'Error'

        response = {'header': header, 'payload': result}

        _LOGGER.info("[%s] Respnose:\n%s", LOGGER_NAME, response)
        return response

    def _prase_command(self, command, arg):
        header = command['header']
        payload = command['payload']

        if arg == 'device_id':
            return payload['device']['id']
        elif arg == 'action':
            return header['name']
        elif arg == 'user_uid':
            return payload.get('openUid','')
        else:
            return command.get(arg)

    def _discovery_process_propertites(self, device_properties):
        properties = []
        for device_property in device_properties:
            name = self.device_attribute_map_h2p.get(device_property.get('attribute'))
            state = self._hass.states.get(device_property.get('entity_id'))
            if name and state:
                value = state.state
                if name == 'power_state':
                    if state.state != 'off':
                        value = 'on'
                    else:
                        value = 'off'

                properties += [{'name': name, 'value': value, 'scale': DEVICE_ATTRIBUTE_DICT.get(name, {}).get('scale'), 'timestampOfSample': int(time.time()), 'uncertaintyInMilliseconds': 1000, 'legalValue': DEVICE_ATTRIBUTE_DICT.get(name, {}).get('legalValue') }]
                
        return properties if properties else [{'name': 'power_state', 'value': 'off', 'scale': DEVICE_ATTRIBUTE_DICT.get('power_state', {}).get('scale'), 'timestampOfSample': int(time.time()), 'uncertaintyInMilliseconds': 1000, 'legalValue': DEVICE_ATTRIBUTE_DICT.get('power_state', {}).get('legalValue') }]
    
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
        return self.device_type_map_h2p.get(raw_device_type)

    def _discovery_process_device_info(self, device_id,  device_type, device_name, zone, properties, actions):
        return {
            'deviceId': encrypt_device_id(device_id),
            'deviceName': {'cn':device_name,'en':'undefined'},
            'type': device_type,
            'zone': zone,
            'isReachable': True,
            'manufacturerName': 'HomeAssistant',
            'modelName': 'HomeAssistant',
            'version': '1.0',
            'actions': actions,
            'properties': properties,
            }


    def _control_process_propertites(self, device_properties, action) -> None:
        
        return self._discovery_process_propertites(device_properties)

    def _query_process_propertites(self, device_properties, action) -> None:
        properties = [ ]
        if action in self._query_map_p2h:
            for property_name, attr_template in self._query_map_p2h[action].items():
                formattd_property = self.vcdm.format_property(self._hass, device_properties, attr_template)
                formattd_property.update({'name': property_name})
                properties += [formattd_property]
        else:
            for device_property in device_properties:
                state = self._hass.states.get(device_property.get('entity_id'))
                value = state.attributes.get(device_property.get('attribute'), state.state) if state else None
                if value:
                    if device_property.get('attribute').lower() in action.lower() or action == 'query_all':
                        name = device_property.get('attribute')
                        formattd_property = {'name': name, 'value': value, 'scale': DEVICE_ATTRIBUTE_DICT.get(name, {}).get('scale')}
                        properties += [formattd_property]
        return properties

    def _decrypt_device_id(self, device_id) -> None:
        return decrypt_device_id(device_id)

    # def report_device(self, device_id):

    #     payload = []
    #     for p_user_id in self._hass.data[INTEGRATION][DATA_HAVCS_BIND_MANAGER].get_uids(DOMAIN, entity_device_idid):
    #         _LOGGER.info("[%s] report device for %s:\n", LOGGER_NAME, p_user_id)
    #         report = {
    #             "header": {
    #                 "namespace": "DuerOS.ConnectedHome.Control",
    #                 "name": "ChangeReportRequest",
    #                 "messageId": str(uuid.uuid4()),
    #                 "payloadVersion": "1"
    #             },
    #             "payload": {
    #                 "botId": "",
    #                 "openUid": p_user_id,
    #                 "appliance": {
    #                     "applianceId": encrypt_entity_id(device_id),
    #                     "attributeName": "turnOnState"
    #                 }
    #             }
    #         }
    #         payload.append(report)
    #     return payload