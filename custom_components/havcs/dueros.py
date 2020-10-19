import json
import uuid
import time
import logging

from .util import decrypt_device_id, encrypt_device_id
from .helper import VoiceControlProcessor, VoiceControlDeviceManager
from .const import DATA_HAVCS_BIND_MANAGER, INTEGRATION, ATTR_DEVICE_ACTIONS

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)

DOMAIN = 'dueros'
LOGGER_NAME = 'dueros'

async def createHandler(hass, entry):
    mode = ['handler']
    return VoiceControlDueros(hass, mode, entry)

class PlatformParameter:
    device_attribute_map_h2p = {
        'temperature': 'temperature',
        'brightness': 'brightness',
        'humidity': 'humidity',
        'pm25': 'pm2.5',
        'co2': 'co2',
        'power_state': 'turnOnState',
        'mode': 'mode'
    }
    device_action_map_h2p ={
        'turn_on': 'turnOn',
        'turn_off': 'turnOff',
        'timing_turn_on': 'timingTurnOn',
        'timing_turn_off': 'timingTurnOff',
        'increase_brightness': 'incrementBrightnessPercentage',
        'decrease_brightness': 'decrementBrightnessPercentage',
        'set_brightness': 'setBrightnessPercentage',
        # 'increase_temperature': 'incrementTemperature',
        # 'decrease_temperature': 'decrementTemperature',
        # 'set_temperature': 'setTemperature',
        'set_color': 'setColor',
        'pause': 'pause',
        # 'query_color': 'QueryColor',
        # 'query_power_state': 'getTurnOnState',
        'query_temperature': 'getTemperatureReading',
        'query_humidity': 'getHumidity',
        'set_mode': 'setMode'
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
        'SWITCH': '开关',
        'SOCKET': '插座',
        'CURTAIN': '窗帘',
        'CURT_SIMP': '窗纱',
        'AIR_CONDITION': '空调',
        'TV_SET': '电视机',
        'SET_TOP_BOX': '机顶盒',
        'AIR_MONITOR': '空气监测器',
        'AIR_PURIFIER': '空气净化器',
        'WATER_PURIFIER': '净水器',
        'HUMIDIFIER': '加湿器',
        'FAN': '电风扇',
        'WATER_HEATER': '热水器',
        'HEATER': '电暖器',
        'WASHING_MACHINE': '洗衣机',
        'CLOTHES_RACK': '晾衣架',
        'GAS_STOVE': '燃气灶',
        'RANGE_HOOD': '油烟机',
        'OVEN': '烤箱设备',
        'MICROWAVE_OVEN': '微波炉',
        'PRESSURE_COOKER': '压力锅',
        'RICE_COOKER': '电饭煲',
        'INDUCTION_COOKER': '电磁炉',
        'HIGH_SPEED_BLENDER': '破壁机',
        'SWEEPING_ROBOT': '扫地机器人',
        'FRIDGE': '冰箱',
        'PRINTER': '打印机',
        'AIR_FRESHER': '新风机',
        'KETTLE': '热水壶',
        'WEBCAM': '摄像头',
        'ROBOT': '机器人',
        'WINDOW_OPENER': '开窗器',
        'DISINFECTION_CABINET': '消毒柜',
        'DISHWASHER': '洗碗机',
        'ACTIVITY_TRIGGER': '描述特定设备的组合场景',
        'SCENE_TRIGGER': '描述特定设备的组合场景',
        'SOFA': '沙发',
        'BED': '床',
        'SHOE_CABINET': '鞋柜',
    }

    device_type_map_h2p = {
        'climate': 'AIR_CONDITION',
        'fan': 'FAN',
        'light': 'LIGHT',
        'media_player': 'TV_SET',
        'switch': 'SWITCH',
        'sensor': 'SENSOR',
        'cover': 'CURTAIN',
        'vacuum': 'SWEEPING_ROBOT',
        }

    _service_map_p2h = {
        # 模式和平台设备类型不影响
        'fan': {
            'SetModeRequest': lambda state, attributes, payload: (['fan'], ['set_speed'], [{"speed": payload['mode']['value'].lower()}])
        },
        'cover': {
            'TurnOnRequest':  'open_cover',
            'TurnOffRequest': 'close_cover',
            'TimingTurnOnRequest': 'open_cover',
            'TimingTurnOffRequest': 'close_cover',
            'PauseRequest': 'stop_cover',
        },
        'vacuum': {
            'TurnOnRequest':  'start',
            'TurnOffRequest': 'return_to_base',
            'TimingTurnOnRequest': 'start',
            'TimingTurnOffRequest': 'return_to_base',
            'SetSuctionRequest': lambda state, attributes, payload: (['vacuum'], ['set_fan_speed'], [{'fan_speed': 90 if payload['suction']['value'] == 'STRONG' else 60}]),
        },
        'switch': {
            'TurnOnRequest': 'turn_on',
            'TurnOffRequest': 'turn_off',
            'TimingTurnOnRequest': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'on', 'duration': int(payload['timestamp']['value']) - int(time.time())}]),
            'TimingTurnOffRequest': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'off', 'duration': int(payload['timestamp']['value']) - int(time.time())}])
        },
        'light': {
            'TurnOnRequest': 'turn_on',
            'TurnOffRequest': 'turn_off',
            'TimingTurnOnRequest': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'on', 'duration': int(payload['timestamp']['value']) - int(time.time())}]),
            'TimingTurnOffRequest': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'off', 'duration': int(payload['timestamp']['value']) - int(time.time())}]),
            'SetBrightnessPercentageRequest': lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': payload['brightness']['value']}]),
            'IncrementBrightnessPercentageRequest': lambda state, attributes, payload: (['light'], ['turn_on'],[ {'brightness_pct': min(state.attributes['brightness'] / 255 * 100 + payload['deltaPercentage']['value'], 100)}]),
            'DecrementBrightnessPercentageRequest': lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': max(state.attributes['brightness'] / 255 * 100 - payload['deltaPercentage']['value'], 0)}]),
            'SetColorRequest': lambda state, attributes, payload: (['light'], ['turn_on'], [{'hs_color': [float(payload['color']['hue']), float(payload['color']['saturation']) * 100], 'brightness_pct': float(payload['color']['brightness']) * 100}])
        },
        'havcs':{
            'TurnOnRequest': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_on']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_on']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_on']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_on'], [{}]),
            'TurnOffRequest': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_off']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_off']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['turn_off']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_off'], [{}]),
            'IncrementBrightnessPercentageRequest': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['increase_brightness']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['increase_brightness']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['increase_brightness']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_on'], [{}]),
            'DecrementBrightnessPercentageRequest': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['decrease_brightness']], [cmnd[1] for cmnd in attributes[ATTR_DEVICE_ACTIONS]['decrease_brightness']], [json.loads(cmnd[2]) for cmnd in attributes[ATTR_DEVICE_ACTIONS]['decrease_brightness']]) if attributes.get(ATTR_DEVICE_ACTIONS) else (['input_boolean'], ['turn_on'], [{}]),                 
            'TimingTurnOnRequest': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'custom:havcs_actions/timing_turn_on', 'duration': int(payload['timestamp']['value']) - int(time.time())}]),
            'TimingTurnOffRequest': lambda state, attributes, payload: (['common_timer'], ['set'], [{'operation': 'custom:havcs_actions/timing_turn_off', 'duration': int(payload['timestamp']['value']) - int(time.time())}]),
        }

    }
    # action:[{Platfrom Attr: HA Attr},{}]
    _query_map_p2h = {
        'GetTemperatureReadingRequest':{'temperatureReading':{'value':'%temperature',"scale": "CELSIUS"}}
    }

class VoiceControlDueros(PlatformParameter, VoiceControlProcessor):
    def __init__(self, hass, mode, entry):
        self._hass = hass
        self._mode = mode
        self.vcdm = VoiceControlDeviceManager(entry, DOMAIN, self.device_action_map_h2p, self.device_attribute_map_h2p, self._service_map_p2h, self.device_type_map_h2p, self._device_type_alias)
    def _errorResult(self, errorCode, messsage=None):
        """Generate error result"""
        error_code_map = {
            'INVALIDATE_CONTROL_ORDER': 'invalidate control order',
            'SERVICE_ERROR': 'TargetConnectivityUnstableError',
            'DEVICE_NOT_SUPPORT_FUNCTION': 'NotSupportedInCurrentModeError',
            'INVALIDATE_PARAMS': 'ValueOutOfRangeError',
            'DEVICE_IS_NOT_EXIST': 'DriverInternalError',
            'IOT_DEVICE_OFFLINE': 'TargetOfflineError',
            'ACCESS_TOKEN_INVALIDATE': 'InvalidAccessTokenError'            
        }
        messages = {
            'INVALIDATE_CONTROL_ORDER': 'invalidate control order',
            'SERVICE_ERROR': 'service error',
            'DEVICE_NOT_SUPPORT_FUNCTION': 'device not support',
            'INVALIDATE_PARAMS': 'invalidate params',
            'DEVICE_IS_NOT_EXIST': 'device is not exist',
            'IOT_DEVICE_OFFLINE': 'device is offline',
            'ACCESS_TOKEN_INVALIDATE': 'access_token is invalidate'
        }
        return {'errorCode': error_code_map.get(errorCode, 'undefined'), 'message': messsage if messsage else messages.get(errorCode, 'undefined')}

    async def handleRequest(self, data, auth = False, request_from = "http"):
        """Handle request"""
        _LOGGER.info("[%s] Handle Request:\n%s", LOGGER_NAME, data)

        header = self._prase_command(data, 'header')
        action = self._prase_command(data, 'action')
        namespace = self._prase_command(data, 'namespace')
        p_user_id = self._prase_command(data, 'user_uid')
        result = {}
        # uid = p_user_id+'@'+DOMAIN

        if auth:
            namespace = header['namespace']
            if namespace == 'DuerOS.ConnectedHome.Discovery':
                action = 'DiscoverAppliancesResponse'
                err_result, discovery_devices, entity_ids = self.process_discovery_command(request_from)
                result = {'discoveredAppliances': discovery_devices}
                if DATA_HAVCS_BIND_MANAGER in self._hass.data[INTEGRATION]:
                    await self._hass.data[INTEGRATION][DATA_HAVCS_BIND_MANAGER].async_save_changed_devices(entity_ids, DOMAIN, p_user_id)
            elif namespace == 'DuerOS.ConnectedHome.Control':
                err_result, properties = await self.process_control_command(data)
                result = err_result if err_result else {'attributes': properties}
                action = action.replace('Request', 'Confirmation') # fix
            elif namespace == 'DuerOS.ConnectedHome.Query':
                err_result, properties = self.process_query_command(data)
                result = err_result if err_result else properties
                action = action.replace('Request', 'Response') # fix 主动上报会收到ReportStateRequest action，可以返回设备的其他属性信息不超过10个
            else:
                result = self._errorResult('SERVICE_ERROR')
        else:
            result = self._errorResult('ACCESS_TOKEN_INVALIDATE')
        
        # Check error
        header['name'] = action
        if 'errorCode' in result:
            header['name'] = result['errorCode']
            result={}

        response = {'header': header, 'payload': result}

        _LOGGER.info("[%s] Respnose:\n%s", LOGGER_NAME, response)
        return response

    def _prase_command(self, command, arg):
        header = command['header']
        payload = command['payload']

        if arg == 'device_id':
            return payload['appliance']['applianceId']
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
            if name:
                value = state.state if state else 'unavailable'
                if name == 'temperature':
                    scale = 'CELSIUS'
                    legalValue = 'DOUBLE'
                elif name == 'brightness':
                    scale = '%'
                    legalValue = '[0.0, 100.0]'
                elif name == 'formaldehyde':
                    scale = 'mg/m3'
                    legalValue = 'DOUBLE'
                elif name == 'humidity':
                    scale = '%'
                    legalValue = '[0.0, 100.0]'
                elif name == 'pm25':
                    scale = 'μg/m3'
                    legalValue = '[0.0, 1000.0]'
                elif name == 'co2':
                    scale = 'ppm'
                    legalValue = 'INTEGER'
                elif name == 'turnOnState':
                    if value != 'on':
                        value = 'OFF'
                    else:
                        value = 'ON'
                    scale = ''
                    legalValue = '(ON, OFF)'
                elif name == 'mode':
                    scale = ''
                    legalValue = '(POWERFUL, NORMAL, QUIET)'
                else:
                    _LOGGER.warning("[%s] %s has unsport attribute %s", LOGGER_NAME, device_property.get('entity_id'), name)
                    continue
                properties += [{'name': name, 'value': value, 'scale': scale, 'timestampOfSample': int(time.time()), 'uncertaintyInMilliseconds': 1000, 'legalValue': legalValue }]
                
        return properties if properties else [{'name': 'turnOnState', 'value': 'OFF', 'scale': '', 'timestampOfSample': int(time.time()), 'uncertaintyInMilliseconds': 1000, 'legalValue': '(ON, OFF)' }]
        
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
            'applianceId': encrypt_device_id(device_id),
            'friendlyName': device_name,
            'friendlyDescription': device_name,
            'additionalApplianceDetails': [],
            'applianceTypes': [device_type],
            'isReachable': True,
            'manufacturerName': 'HomeAssistant',
            'modelName': 'HomeAssistant',
            'version': '1.0',
            'actions': actions,
            'attributes': properties,
            }


    def _control_process_propertites(self, device_properties, action) -> None:
        
        return self._discovery_process_propertites(device_properties)

    def _query_process_propertites(self, device_properties, action) -> None:
        properties = {}
        action = action.replace('Request', '').replace('Get', '')
        if action in self._query_map_p2h:
            for property_name, attr_template in self._query_map_p2h[action].items():
                formattd_property = self.vcdm.format_property(self._hass, device_properties, attr_template)
                properties.update({property_name:formattd_property})
        else:
            for device_property in device_properties:
                state = self._hass.states.get(device_property.get('entity_id'))
                value = state.attributes.get(device_property.get('attribute'), state.state) if state else None
                if value:
                    if device_property.get('attribute').lower() in action.lower():
                        name = action[0].lower() + action[1:]
                        formattd_property = {name: {'value': value}}  
                        properties.update(formattd_property)
        return properties

    def _decrypt_device_id(self, device_id) -> None:
        return decrypt_device_id(device_id)

    def report_device(self, device_id):

        payload = []
        for p_user_id in self._hass.data[INTEGRATION][DATA_HAVCS_BIND_MANAGER].get_uids(DOMAIN, device_id):
            _LOGGER.info("[%s] report device for %s:\n", LOGGER_NAME, p_user_id)
            report = {
                "header": {
                    "namespace": "DuerOS.ConnectedHome.Control",
                    "name": "ChangeReportRequest",
                    "messageId": str(uuid.uuid4()),
                    "payloadVersion": "1"
                },
                "payload": {
                    "botId": "",
                    "openUid": p_user_id,
                    "appliance": {
                        "applianceId": encrypt_device_id(device_id),
                        "attributeName": "turnOnState"
                    }
                }
            }
            payload.append(report)
        return payload