import json, math, time
import logging

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (MAJOR_VERSION, MINOR_VERSION)
from homeassistant.auth.const import ACCESS_TOKEN_EXPIRATION
import uuid
import homeassistant.auth.models as models
from typing import Optional
from datetime import timedelta
from homeassistant.helpers.state import AsyncTrackStates
from urllib.request import urlopen
import copy
from .util import (decrypt_device_id, encrypt_entity_id, DOMAIN_SERVICE_WITHOUT_ENTITY_ID, AIHOME_ACTIONS_ALIAS)

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)

AI_HOME = True
DOMAIN = 'dueros'

def createHandler(hass):
    return Dueros(hass)

class Dueros:
    def __init__(self, hass):
        self._hass = hass
        self._DEVICE_TYPES = {
            'LIGHT': '电灯',
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
            'SWEEPING_ROBOT':  '扫地机器人',
            'FRIDGE': '冰箱',
            'PRINTER': '打印机',
            'AIR_FRESHER': '新风机',
            'KETTLE': '热水壶',
            'WEBCAM': '摄像头',
            'ROBOT': '机器人',
            'WINDOW_OPENER': '开窗器',
            'ACTIVITY_TRIGGER': '特定设备顺序操作组合场景',
            'SCENE_TRIGGER': '特定设备无顺序操作组合场景',
        }

        self._INCLUDE_DOMAINS = {
            'climate': 'AIR_CONDITION',
            'fan': 'FAN',
            'light': 'LIGHT',
            'media_player': 'TV_SET',
            'switch': 'SWITCH',
            'vacuum': 'SWEEPING_ROBOT',
            'sensor': 'SENSOR',
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

        self._ALL_ACTIONS = [
            'turnOn',  # 打开
            'timingTurnOn',  # 定时打开
            'turnOff',  # 关闭
            'timingTurnOff',  # 定时关闭
            'pause',  # 暂停
            'continue',  # 继续
            'setBrightnessPercentage',  # 设置灯光亮度
            'incrementBrightnessPercentage',  # 调亮灯光
            'decrementBrightnessPercentage',  # 调暗灯光
            'incrementTemperature',  # 升高温度
            'decrementTemperature',  # 降低温度
            'setTemperature',  # 设置温度
            'incrementVolume',  # 调高音量
            'decrementVolume',  # 调低音量
            'setVolume',  # 设置音量
            'setVolumeMute',  # 设置设备静音状态
            'incrementFanSpeed',  # 增加风速
            'decrementFanSpeed',  # 减小风速
            'setFanSpeed',  # 设置风速
            'setMode',  # 设置模式
            'unSetMode',  # 取消设置的模式
            'timingSetMode',  # 定时设置模式
            'timingUnsetMode',  # 定时取消设置的模式
            'setColor',  # 设置颜色
            'getAirQualityIndex',  # 查询空气质量
            'getAirPM25',  # 查询PM2.5
            'getTemperatureReading',  # 查询温度
            'getTargetTemperature',  # 查询目标温度
            'getHumidity',  # 查询湿度
            'getTimeLeft',  # 查询剩余时间
            'getRunningTime',  # 查询运行时间
            'getRunningStatus',  # 查询运行状态
            'getWaterQuality',  # 查询水质
            'setHumidity',  # 设置湿度模式
            'setLockState',  # 上锁解锁
            'getLockState',  # 查询锁状态
            'incrementPower',  # 增大功率
            'decrementPower',  # 减小功率
            'returnTVChannel',  # 返回上个频道
            'decrementTVChannel',  # 上一个频道
            'incrementTVChannel',  # 下一个频道
            'setTVChannel',  # 设置频道
            'decrementHeight',  # 降低高度
            'incrementHeight',  # 升高高度
            'chargeTurnOn',  # 开始充电
            'chargeTurnOff',  # 停止充电
            'submitPrint', #打印
            'getTurnOnState', #查询设备打开状态
            'setSuction',  # 设置吸力
            'setDirection',  # 设置移动方向
            'getElectricityCapacity',  # 查询电量
            'getOilCapacity',  # 查询油量
        ]

        self._TRANSLATIONS = {
            'cover': {
                'TurnOnRequest':  'open_cover',
                'TurnOffRequest': 'close_cover',
                'TimingTurnOnRequest': 'open_cover',
                'TimingTurnOffRequest': 'close_cover',
            },
            'vacuum': {
                'TurnOnRequest':  'start',
                'TurnOffRequest': 'return_to_base',
                'TimingTurnOnRequest': 'start',
                'TimingTurnOffRequest': 'return_to_base',
                'SetSuctionRequest': lambda state, payload: (['vacuum'], ['set_fan_speed'], [{'fan_speed': 90 if payload['suction']['value'] == 'STRONG' else 60}]),
            },
            'switch': {
                'TurnOnRequest': 'turn_on',
                'TurnOffRequest': 'turn_off',
                'TimingTurnOnRequest': 'turn_on',
                'TimingTurnOffRequest': 'turn_off'
            },
            'light': {
                'TurnOnRequest':  'turn_on',
                'TurnOffRequest': 'turn_off',
                'TimingTurnOnRequest': 'turn_on',
                'TimingTurnOffRequest': 'turn_off',
                'SetBrightnessPercentageRequest': lambda state, payload: (['light'], ['turn_on'], [{'brightness_pct': payload['brightness']['value']}]),
                'IncrementBrightnessPercentageRequest': lambda state, payload: (['light'], ['turn_on'],[ {'brightness_pct': min(state.attributes['brightness'] / 255 * 100 + payload['deltaPercentage']['value'], 100)}]),
                'DecrementBrightnessPercentageRequest': lambda state, payload: (['light'], ['turn_on'], [{'brightness_pct': max(state.attributes['brightness'] / 255 * 100 - payload['deltaPercentage']['value'], 0)}]),
                'SetColorRequest': lambda state, payload: (['light'], ['turn_on'], [{"hs_color": [float(payload['color']['hue']), float(payload['color']['saturation']) * 100]}])
            },
            'input_boolean':{
                'TurnOnRequest': lambda state, payload:([cmnd[0] for cmnd in state.attributes['aihome_actions']['turn_on']], [cmnd[1] for cmnd in state.attributes['aihome_actions']['turn_on']], [json.loads(cmnd[2]) for cmnd in state.attributes['aihome_actions']['turn_on']]) if state.attributes.get('aihome_actions') else (['input_boolean'], ['turn_on'], [{}]),
                'TurnOffRequest': lambda state, payload:([cmnd[0] for cmnd in state.attributes['aihome_actions']['turn_off']], [cmnd[1] for cmnd in state.attributes['aihome_actions']['turn_off']], [json.loads(cmnd[2]) for cmnd in state.attributes['aihome_actions']['turn_off']]) if state.attributes.get('aihome_actions') else (['input_boolean'], ['turn_off'], [{}]),
                'IncrementBrightnessPercentageRequest': lambda state, payload:([cmnd[0] for cmnd in state.attributes['aihome_actions']['increase_brightness']], [cmnd[1] for cmnd in state.attributes['aihome_actions']['increase_brightness']], [json.loads(cmnd[2]) for cmnd in state.attributes['aihome_actions']['increase_brightness']]) if state.attributes.get('aihome_actions') else (['input_boolean'], ['turn_on'], [{}]),
                'DecrementBrightnessPercentageRequest': lambda state, payload:([cmnd[0] for cmnd in state.attributes['aihome_actions']['decrease_brightness']], [cmnd[1] for cmnd in state.attributes['aihome_actions']['decrease_brightness']], [json.loads(cmnd[2]) for cmnd in state.attributes['aihome_actions']['decrease_brightness']]) if state.attributes.get('aihome_actions') else (['input_boolean'], ['turn_on'], [{}]),
            }

        }
    def _errorResult(self, errorCode, messsage=None):
        """Generate error result"""
        messages = {
            'INVALIDATE_CONTROL_ORDER':    'invalidate control order',
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
        _LOGGER.info("Handle Request: %s", data)
        header = data['header']
        payload = data['payload']
        attributes = None
        name = header['name']
        p_user_id = payload.get('openUid','')
        # uid = p_user_id+'@'+DOMAIN

        if auth:
            namespace = header['namespace']
            if namespace == 'DuerOS.ConnectedHome.Discovery':
                name = 'DiscoverAppliancesResponse'
                discovery_devices,entity_ids = self._discoveryDevice()
                result = {'discoveredAppliances': discovery_devices}
                await self._hass.data['aihome_bind_manager'].async_save_changed_devices(entity_ids, DOMAIN, p_user_id)
            elif namespace == 'DuerOS.ConnectedHome.Control':
                result = await self._controlDevice(name, payload)
                name = name.replace('Request', 'Confirmation') # fix
            elif namespace == 'DuerOS.ConnectedHome.Query':
                result = self._queryDevice(name, payload)
                name = name.replace('Request', 'Response') # fix
            else:
                result = self._errorResult('SERVICE_ERROR')
        else:
            result = self._errorResult('ACCESS_TOKEN_INVALIDATE')
        
        _LOGGER.info("Handle result: %s", result)
        # Check error
        header['name'] = name
        if 'errorCode' in result:
            header['name'] = 'DriverInternalError'
            result={}

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

            if not attributes.get('aihome_device', False):
                continue

            friendly_name = attributes.get('friendly_name')
            if friendly_name is None:
                continue

            entity_id = state.entity_id

            deviceTypes = self._guessDeviceType(entity_id, attributes)
            if deviceTypes is None:
                continue

            properties,actions = self._guessPropertyAndAction(entity_id, attributes)
            device_attr =[]
            _LOGGER.debug('-----entity_id: %s, deviceTypes: %s, attributes: %s', entity_id, deviceTypes, attributes)
            if 'sensor' in deviceTypes:
                if attributes.get('aihome_sensor_group') is None:
                    continue

                sensor_ids = self._hass.states.get(attributes.get('aihome_sensor_group')).attributes.get('entity_id')
                for sensor in sensor_ids:
                    if sensor.startswith('sensor.'):
                        prop,action = self._guessPropertyAndAction(sensor, self._hass.states.get(sensor).attributes, self._hass.states.get(sensor).state)
                        actions += action
                        device_attr.append(prop) 
                actions = list(set(actions))
                deviceTypes = ['AIR_MONITOR']

            devices.append({
                'applianceId': encrypt_entity_id(entity_id),
                'friendlyName': friendly_name,
                'friendlyDescription': friendly_name,
                'additionalApplianceDetails': [],
                'applianceTypes': deviceTypes,
                'isReachable': True,
                'manufacturerName': 'HomeAssistant',
                'modelName': 'HomeAssistant',
                'version': '1.0',
                'actions': actions,
                'attributes': device_attr if device_attr else properties,
                })
            entity_ids.append(entity_id)
        return devices, entity_ids

        # return {
        #     "discoveredAppliances": [],
        #     "discoveredGroups": [{
        #         "groupName": "myGroup",
        #         "applianceIds": []
        #     }]
        # }

    async def _controlDevice(self, cmnd, payload):
        entity_id = decrypt_device_id(payload['appliance']['applianceId'])
        domain = entity_id[:entity_id.find('.')]
        data = {"entity_id": entity_id }
        domain_list = [domain]
        data_list = [data]
        service_list =['']
        if domain in self._TRANSLATIONS.keys():
            translation = self._TRANSLATIONS[domain][cmnd]
            if callable(translation):
                domain_list, service_list, data_list = translation(self._hass.states.get(entity_id), payload)
                _LOGGER.debug('domain_list: %s', domain_list)
                _LOGGER.debug('service_list: %s', service_list)
                _LOGGER.debug('data_list: %s', data_list)
                for i,d in enumerate(data_list):
                    if 'entity_id' not in d and domain_list[i] not in DOMAIN_SERVICE_WITHOUT_ENTITY_ID:
                        d.update(data)
            else:
                service_list[0] = translation
        else:
            service_list[0] = self._getControlService(cmnd)

        for i in range(len(domain_list)):
            _LOGGER.debug('domain: %s, servcie: %s, data: %s', domain_list[i], service_list[i], data_list[i])
            with AsyncTrackStates(self._hass) as changed_states:
                result = await self._hass.services.async_call(domain_list[i], service_list[i], data_list[i], True)
            if not result:
                return self._errorResult('IOT_DEVICE_OFFLINE')
        state = self._hass.states.get(entity_id)
        properties,actions = self._guessPropertyAndAction(entity_id, state.attributes, state.state)
        return {'attributes': [properties]}

    def _queryDevice(self, cmnd, payload):
        applianceDic = payload['appliance']
        entity_id = decrypt_device_id(applianceDic['applianceId'])
        state = self._hass.states.get(entity_id)

        if entity_id.startswith('sensor.'):
            entity_ids = self._hass.states.get(state.attributes.get('aihome_sensor_group')).attributes.get('entity_id')

            properties = []
            for entity_id in entity_ids:
                entity = self._hass.states.get(entity_id)
                if entity_id.startswith('sensor.') and entity.attributes.get('aihome_sensor') is not None :
                    prop,action = self._guessPropertyAndAction(entity_id, entity.attributes, entity.state)
                    _LOGGER.debug('property:%s', prop)
                    if prop is None:
                        continue
                    elif prop.get('name').lower() in cmnd.lower():
                        name = cmnd.replace('Request', '').replace('Get', '')
                        name = name[0].lower() + name[1:]
                        properties = {name: {'value': prop.get('value')}}
                        break
            return properties if properties else self._errorResult('IOT_DEVICE_OFFLINE')
        else:
            if state is not None and state.state != 'unavailable':
                # return {'name':'turnOnState', 'value':state.state}
                properties,actions = self._guessPropertyAndAction(entity_id, state.attributes, state.state)
                return {'attributes': [properties]}
        return self._errorResult('IOT_DEVICE_OFFLINE')

    def _getControlService(self, action):
        i = 0
        service = ''
        for c in action.split('Request')[0]:
            service += (('_' if i else '') + c.lower()) if c.isupper() else c
            i += 1
        return service


    def _guessDeviceType(self, entity_id, attributes):
        deviceTypes = []
        if 'dueros_deviceType' in attributes:
            deviceTypes.append(attributes['dueros_deviceType'])

        # Exclude with domain
        domain = entity_id[:entity_id.find('.')]
        if domain in self._EXCLUDE_DOMAINS:
            return None

        # Guess from entity_id
        for deviceType in self._DEVICE_TYPES.keys():
            if deviceType in entity_id:
                deviceTypes.append(deviceType)

        # Map from domain
        if domain in self._INCLUDE_DOMAINS:
            deviceTypes.append(self._INCLUDE_DOMAINS[domain])

        return [device.upper() for device in deviceTypes]


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
        if 'dueros_actions' in attributes:
            actions = copy.deepcopy(attributes['dueros_actions']) # fix
        elif 'aihome_actions' in attributes:
            actions = [AIHOME_ACTIONS_ALIAS[DOMAIN].get(action) for action in attributes['aihome_actions'].keys() if AIHOME_ACTIONS_ALIAS[DOMAIN].get(action)]
            _LOGGER.debug('[%s] guess action from aihome standard action: %s', entity_id, actions)
        elif entity_id.startswith('switch.'):
            actions = ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff"]
        elif entity_id.startswith('light.'):
            actions = ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff", "setBrightnessPercentage", "incrementBrightnessPercentage", "decrementBrightnessPercentage", "setColor"]
        elif entity_id.startswith('cover.'):
            actions = ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff", "pause"]
        elif entity_id.startswith('vacuum.'):
            actions = ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff", "setSuction"]
        elif entity_id.startswith('sensor.'):
            actions = ["getTemperatureReading", "getHumidity"]
        else:
            actions = ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff"]

        if 'dueros_property' in attributes:
            name = attributes['dueros_property']
        elif entity_id.startswith('sensor.'):
            unit = attributes['unit_of_measurement'] if 'unit_of_measurement' in attributes else ''
            if unit == u'°C' or unit == u'℃':
                name = 'temperature'
                scale = 'CELSIUS'
                legalValue = 'DOUBLE'
            elif unit == 'lx' or unit == 'lm':
                name = 'brightness'
            elif ('hcho' in entity_id):
                name = 'formaldehyde'
                scale = 'mg/m3'
                legalValue = 'DOUBLE'
            elif ('humidity' in entity_id):
                name = 'humidity'
                scale = '%'
                legalValue = '[0.0, 100.0]'
            elif ('pm25' in entity_id):
                name = 'pm2.5'
                scale = 'μg/m3'
                legalValue = '[0.0, 1000.0]'
            elif ('co2' in entity_id):
                name = 'co2'
                scale = 'ppm'
                legalValue = 'INTEGER'
            else:
                name = None
        else:
            name = 'turnOnState'
            if state != 'off':
                state = 'ON'
            else:
                state = 'OFF'
            scale = ''
            legalValue = '(ON, OFF)'
        Property = {'name': name, 'value': state, 'scale': scale, 'timestampOfSample': int(time.time()), 'uncertaintyInMilliseconds': 1000, 'legalValue': legalValue } if name is not None else None
        return Property, actions

    def report_device(self, entity_id):

        payload = []
        for p_user_id in self._hass.data['aihome_bind_manager'].get_uids(DOMAIN, entity_id):
            _LOGGER.debug('report_device(): %s', p_user_id)
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
                        "applianceId": encrypt_entity_id(entity_id),
                        "attributeName": "turnOnState"
                    }
                }
            }
            payload.append(report)
        return payload
