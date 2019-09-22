import json
import logging
import uuid
import copy
import time

from .util import decrypt_device_id, encrypt_entity_id
from .helper import VoiceControlProcessor, VoiceControlDeviceManager

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)

AI_HOME = True
DOMAIN = 'jdwhale'
LOGGER_NAME = 'jdwhale'

REPORT_WHEN_STARUP = True

def createHandler(hass):
    mode = ['handler']
    if REPORT_WHEN_STARUP:
        mode.append('report_when_starup')
    return VoiceControlJdwhale(hass, mode)

class PlatformParameter:
    device_attribute_map_h2p = {
        'power_state': 'PowerState',
        'color': 'Color',
        'temperature': 'Temperature',
        'humidity': 'Humidity',
        # '': 'windspeed',
        'brightness': 'Brightness',
        # '': 'direction',
        # '': 'angle',
        'pm25': 'PM25',
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
        'query': 'Query',
        'query_color': 'QueryColor',
        'query_power_state': 'QueryPowerState',
        'query_temperature': 'QueryTemperature',
        'query_humidity': 'QueryHumidity',
        'query_pm25': 'QueryPM25'
    }
    _device_type_alias = {
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
        'cover': {
            'TurnOnRequest':  'open_cover',
            'TurnOffRequest': 'close_cover',
        },
        'vacuum': {
            'TurnOnRequest':  'start',
            'TurnOffRequest': 'return_to_base',
            'SetSuctionRequest': lambda state, attributes, payload: (['fan'], ['set_fan_speed'], [{'fan_speed': 90 if payload['suction']['value'] == 'STRONG' else 60}]),
        },
        'switch': {
            'TurnOnRequest': 'turn_on',
            'TurnOffRequest': 'turn_off',
        },
        'light': {
            'TurnOnRequest':  'turn_on',
            'TurnOffRequest': 'turn_off',
            'SetBrightnessPercentageRequest': lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': payload['brightness']['value']}]),
            'IncrementBrightnessPercentageRequest': lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': min(attributes['brightness'] / 255 * 100 + payload['deltaPercentage']['value'], 100)}]),
            'DecrementBrightnessPercentageRequest': lambda state, attributes, payload: (['light'], ['turn_on'], [{'brightness_pct': max(attributes['brightness'] / 255 * 100 - payload['deltaPercentage']['value'], 0)}]),
            'SetColorRequest': lambda state, attributes, payload: (['light'], ['turn_on'], [{"hs_color": [float(payload['color']['hue']), float(payload['color']['saturation']) * 100]}])
        },
        'input_boolean':{
            'TurnOnRequest': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes['havcs_actions']['turn_on']], [cmnd[1] for cmnd in attributes['havcs_actions']['turn_on']], [json.loads(cmnd[2]) for cmnd in attributes['havcs_actions']['turn_on']]) if attributes.get('havcs_actions') else (['input_boolean'], ['turn_on'], [{}]),
            'TurnOffRequest': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes['havcs_actions']['turn_off']], [cmnd[1] for cmnd in attributes['havcs_actions']['turn_off']], [json.loads(cmnd[2]) for cmnd in attributes['havcs_actions']['turn_off']]) if attributes.get('havcs_actions') else (['input_boolean'], ['turn_off'], [{}]),
            'AdjustUpBrightnessRequest': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes['havcs_actions']['increase_brightness']], [cmnd[1] for cmnd in attributes['havcs_actions']['increase_brightness']], [json.loads(cmnd[2]) for cmnd in attributes['havcs_actions']['increase_brightness']]) if attributes.get('havcs_actions') else (['input_boolean'], ['turn_on'], [{}]),
            'AdjustDownBrightnessRequest': lambda state, attributes, payload:([cmnd[0] for cmnd in attributes['havcs_actions']['decrease_brightness']], [cmnd[1] for cmnd in attributes['havcs_actions']['decrease_brightness']], [json.loads(cmnd[2]) for cmnd in attributes['havcs_actions']['decrease_brightness']]) if attributes.get('havcs_actions') else (['input_boolean'], ['turn_on'], [{}]),
        }
    }
    _controlSpeech_template = {
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
    _query_map_p2h = {

    }

class VoiceControlJdwhale(PlatformParameter, VoiceControlProcessor):
    def __init__(self, hass, mode):
        self._hass = hass
        self._mode = mode
        self.vcdm = VoiceControlDeviceManager(DOMAIN, self.device_action_map_h2p, self.device_attribute_map_h2p, self._service_map_p2h, self.device_type_map_h2p, self._device_type_alias)
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

    async def handleRequest(self, data, auth = False):
        """Handle request"""
        _LOGGER.info("[%s] Handle Request:\n%s", LOGGER_NAME, data)

        header = self._prase_command(data, 'header')
        payload = self._prase_command(data, 'payload')
        action = self._prase_command(data, 'action')
        namespace = self._prase_command(data, 'namespace')
        p_user_id = self._prase_command(data, 'user_uid')
        # uid = p_user_id+'@'+DOMAIN
        content = {}

        if auth:
            if namespace == 'Alpha.Iot.Device.Discover':
                err_result, discovery_devices, entity_ids = self.process_discovery_command()
                content = {'deviceInfo': discovery_devices}
                await self._hass.data['havcs_bind_manager'].async_save_changed_devices(entity_ids, DOMAIN, p_user_id)
            elif namespace == 'Alpha.Iot.Device.Control':
                err_result, content = await self.process_control_command(data)
            elif namespace == 'Alpha.Iot.Device.Query':
                err_result, content = self.process_query_command(data)
                if not err_result:
                    if len(content)==1:
                        content = content[0]
                    content = {'deviceId': payload['deviceId'], 'properties': content}
            else:
                err_result = self._errorResult('SERVICE_ERROR')
        else:
            err_result = self._errorResult('ACCESS_TOKEN_INVALIDATE')

        # Check error and fill response name
        if err_result:
            header['name'] = 'ErrorResponse'
            content = err_result
            if 'deviceId' in payload:
                content['deviceId'] = payload['deviceId']
        else:
            header['name'] = action.replace('Request','Response')
    
        response = {'header': header, 'payload': content}

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
            return header.get('userId','')
        elif arg == 'namespace':
            return header['namespace']
        else:
            return command.get(arg)

    def _discovery_process_propertites(self, device_properties):
        return {"result": "SUCCESS"}
    
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
        if raw_device_type == 'SENSOR':
            return 'AIR_CLEANER'
        else:
            return raw_device_type

    def _discovery_process_device_info(self, entity_id,  device_type, device_name, zone, properties, actions):
        return {
            'actions': actions,
            'controlSpeech': [self._controlSpeech_template.get(action,'')%(device_name) for action in actions ],
            'deviceId': encrypt_entity_id(entity_id),
            'deviceTypes': device_type,
            'extensions': {'manufacturerName': 'HomeAssistant'},
            'friendlyDescription': device_name,
            'friendlyName': device_name,
            'isReachable': '1',
            'modelName': 'HomeAssistantDevice',
            }

    def _control_process_propertites(self, device_properties, action) -> None:
        return self._discovery_process_propertites(device_properties)

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