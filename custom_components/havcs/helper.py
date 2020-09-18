
import copy
import voluptuous as vol
import asyncio
import logging
import traceback

from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers.state import AsyncTrackStates
from homeassistant.core import HomeAssistant

from .const import DATA_HAVCS_SETTINGS, INTEGRATION, DATA_HAVCS_ITEMS, ATTR_DEVICE_VISABLE, ATTR_DEVICE_ID, ATTR_DEVICE_ENTITY_ID, ATTR_DEVICE_TYPE, ATTR_DEVICE_NAME, ATTR_DEVICE_ZONE, ATTR_DEVICE_ATTRIBUTES, ATTR_DEVICE_ACTIONS, ATTR_DEVICE_PROPERTIES
from .device import VoiceControllDevice


_LOGGER = logging.getLogger(__name__)
LOGGER_NAME = 'helper'

DOMAIN_SERVICE_WITHOUT_ENTITY_ID = ['climate']
DOMAIN_SERVICE_WITH_ENTITY_ID = ['common_timer']

class VoiceControlProcessor:
    def _discovery_process_propertites(self, device_properties) -> None:
        raise NotImplementedError()

    def _discovery_process_actions(self, device_properties, raw_actions) -> None:
        raise NotImplementedError()

    def _discovery_process_device_type(self, raw_device_type) -> None:
        raise NotImplementedError()

    def _discovery_process_device_info(self, device_id, device_type, device_name, zone, properties, actions) -> None:
        raise NotImplementedError()
  
    def _control_process_propertites(self, device_properties, action) -> None:
        raise NotImplementedError()

    def _query_process_propertites(self, device_properties, action) -> None:
        raise NotImplementedError()  

    def _prase_action_p2h(self, action) -> None:
        for k,v in self.vcdm.device_action_map_h2p.items():
            if v == action:
                return k
        i = 0
        service = ''
        for c in action.split('Request')[0]:
            service += (('_' if i else '') + c.lower()) if c.isupper() else c
            i += 1
        return service

    def _decrypt_device_id(self, device_id) -> None:
        raise NotImplementedError()

    def _prase_command(self, command, arg) -> None:
        raise NotImplementedError()
    
    def _errorResult(self, errorCode, messsage=None) -> None:
        raise NotImplementedError()

    vcdm = None
    _hass = None
    _service_map_p2h = None
    def process_discovery_command(self, request_from) -> tuple:
        devices = []
        entity_ids = []
        # fix: 增加响应发现设备信息规则。自建技能或APP技能不启用则不响应对应的发现指令；自建技能与APP技能一起启用只响应APP技能的发现指令。
        if (request_from == self._hass.data[INTEGRATION][DATA_HAVCS_SETTINGS].get('command_filter', '')):
            _LOGGER.debug("[%s] request from %s match filter, return blank info", LOGGER_NAME, request_from)
            return None, devices, entity_ids
        for vc_device in self.vcdm.all(self._hass):
            device_id, raw_device_type, device_name, zone, device_properties, raw_actions = self.vcdm.get_device_attrs(vc_device.attributes)
            properties = self._discovery_process_propertites(device_properties)
            actions = self._discovery_process_actions(device_properties, raw_actions)
            device_type = self._discovery_process_device_type(raw_device_type)
            if None in (device_type, device_name, zone) or [] in (properties, actions):
                _LOGGER.debug("[%s] discovery command: can get all info of entity %s, pass. [device_type = %s, device_name = %s, zone = %s, properties = %s, actions = %s]", LOGGER_NAME, device_id, device_type, device_name, zone, properties, actions)
            else:
                devices.append(self._discovery_process_device_info(device_id, device_type, device_name, zone, properties, actions))
                entity_ids.append(device_id)
        return None, devices, entity_ids

    async def process_control_command(self, command) -> tuple:
        device_id = self._prase_command(command, 'device_id')
        device_id = self._decrypt_device_id(device_id)
        device = self.vcdm.get(device_id)
        if device_id is None or device is None:
            return self._errorResult('DEVICE_IS_NOT_EXIST'), None
        entity_ids=device.entity_id
        action = self._prase_command(command, 'action')
        _LOGGER.debug("[%s] control target info: device_id = %s, name = %s , entity_ids = %s, action = %s", LOGGER_NAME, device.device_id, device.name, entity_ids,action)

        success_task = []

        # 优先使用配置的自定义action，处理逻辑：直接调用自定义service方法
        ha_action = self._prase_action_p2h(action)
        if ha_action in device.custom_actions:
            domain_list = [cmnd[0] for cmnd in device.custom_actions[ha_action]]
            service_list = [cmnd[1] for cmnd in device.custom_actions[ha_action]]
            data_list = [eval(cmnd[2]) for cmnd in device.custom_actions[ha_action]]
            for i in range(len(domain_list)):
                _LOGGER.debug("[%s] %s : domain = %s, servcie = %s, data = %s", LOGGER_NAME, i, domain_list[i], service_list[i], data_list[i])
                with AsyncTrackStates(self._hass) as changed_states:
                    try:
                        result = await self._hass.services.async_call(domain_list[i], service_list[i], data_list[i], True)
                    except (vol.Invalid, ServiceNotFound):
                        _LOGGER.error("[%s] %s : failed to call service\n%s", LOGGER_NAME, i, traceback.format_exc())
                    else:
                        if result:
                            _LOGGER.debug("[%s] %s : success to call service", LOGGER_NAME, i)
                            success_task.append({i: [domain_list[i], service_list[i], data_list[i]]})
                        else:
                            _LOGGER.debug("[%s] %s : failed to call service", LOGGER_NAME, i)
                _LOGGER.debug("[%s] %s : changed_states = %s", LOGGER_NAME, i, changed_states)
        # 自动处理action，处理逻辑：对device的所有entity，执行action对应的service方法
        else:
            for entity_id in entity_ids:
                domain = entity_id[:entity_id.find('.')]
                data = {"entity_id": entity_id }
                domain_list = [domain]
                data_list = [data]
                service_list =['']

                if domain in self._service_map_p2h.keys():
                    translation = self._service_map_p2h[domain][action]
                    if callable(translation):
                        state = self._hass.states.get(entity_id)
                        domain_list, service_list, data_list = translation(state, device.raw_attributes, self._prase_command(command, 'payload'))
                        _LOGGER.debug("[%s] prepared domain_list: %s", LOGGER_NAME, domain_list)
                        _LOGGER.debug("[%s] prepared service_list: %s", LOGGER_NAME, service_list)
                        _LOGGER.debug("[%s] prepared data_list: %s", LOGGER_NAME, data_list)
                        for i,d in enumerate(data_list):
                            if 'entity_id' not in d and (domain_list[i] in DOMAIN_SERVICE_WITH_ENTITY_ID or (domain_list[i] not in DOMAIN_SERVICE_WITHOUT_ENTITY_ID and entity_id.startswith(domain_list[i]+'.'))):
                                d.update(data)
                    else:
                        service_list[0] = translation
                else:
                    service_list[0] = self._prase_action_p2h(action)

                for i in range(len(domain_list)):
                    _LOGGER.debug("[%s] %s @task_%s: domain = %s, servcie = %s, data = %s", LOGGER_NAME, entity_id, i, domain_list[i], service_list[i], data_list[i])
                    with AsyncTrackStates(self._hass) as changed_states:
                        try:
                            result = await self._hass.services.async_call(domain_list[i], service_list[i], data_list[i], True)
                        except (vol.Invalid, ServiceNotFound):
                            _LOGGER.error("[%s] %s @task_%s: failed to call service\n%s", LOGGER_NAME, entity_id, i, traceback.format_exc())
                        else:
                            if result:
                                _LOGGER.debug("[%s] %s @task_%s: success to call service, new state = %s", LOGGER_NAME, entity_id, i, self._hass.states.get(entity_id))
                                success_task.append({entity_id: [domain_list[i], service_list[i], data_list[i]]})
                            else:
                                _LOGGER.debug("[%s] %s @task_%s: failed to call service", LOGGER_NAME, entity_id, i)
                    _LOGGER.debug("[%s] %s @task_%s: changed_states = %s", LOGGER_NAME, entity_id, i, changed_states)
        if not success_task:
            return self._errorResult('IOT_DEVICE_OFFLINE'), None
        # wait 1s for updating state of entity
        await asyncio.sleep(1)
        device_properties = self.vcdm.get(device_id).properties
        properties = self._control_process_propertites(device_properties, action)
        return None, properties

    def process_query_command(self, command) -> tuple:
        device_id = self._prase_command(command, 'device_id')
        device_id = self._decrypt_device_id(device_id)
        if device_id is None:
            return self._errorResult('DEVICE_IS_NOT_EXIST'), None
        action = self._prase_command(command, 'action')
        device_properties = self.vcdm.get(device_id).properties
        properties = self._query_process_propertites(device_properties, action)
        return (None, properties) if properties else (self._errorResult('IOT_DEVICE_OFFLINE'), None)

class VoiceControlDeviceManager:

    def __init__(self, entry, platform, device_action_map_h2p, device_attribute_map_h2p, service_map_p2h, device_type_map_h2p, device_type_alias, device_name_constraints = {}, zone_constraints = []):
        self._entry = entry
        self._platform = platform
        self.device_action_map_h2p = device_action_map_h2p
        self.device_attribute_map_h2p = device_attribute_map_h2p
        self._service_map_p2h = service_map_p2h
        self.device_type_map_h2p = device_type_map_h2p
        self._device_type_alias = device_type_alias
        self._device_name_constraints = device_name_constraints
        self._zone_constraints = zone_constraints
        self._devices_cache = {}
        self._places = ["门口","客厅","卧室","客房","主卧","次卧","书房","餐厅","厨房","洗手间","浴室","阳台",\
        "宠物房","老人房","儿童房","婴儿房","保姆房","玄关","一楼","二楼","三楼","四楼","楼梯","走廊",\
        "过道","楼上","楼下","影音室","娱乐室","工作间","杂物间","衣帽间","吧台","花园","温室","车库","休息室","办公室","起居室"]

    def all(self, hass: HomeAssistant = None, init_flag: bool = False) -> list:
        if not self._devices_cache or init_flag:
            self._devices_cache.clear()
            for device_id, device_attributes in hass.data[INTEGRATION][DATA_HAVCS_ITEMS].items():
                if ATTR_DEVICE_VISABLE not in device_attributes:
                    pass
                elif isinstance(device_attributes.get(ATTR_DEVICE_VISABLE) , str) and self._platform == device_attributes.get(ATTR_DEVICE_VISABLE):
                    pass
                elif isinstance(device_attributes.get(ATTR_DEVICE_VISABLE) , list) and self._platform in device_attributes.get(ATTR_DEVICE_VISABLE):
                    pass
                else:
                    continue
                if isinstance(device_attributes.get(ATTR_DEVICE_ENTITY_ID) , str):
                    device_attributes[ATTR_DEVICE_ENTITY_ID]= [device_attributes.get(ATTR_DEVICE_ENTITY_ID)]

                self._devices_cache.update(self.get(device_id, hass, device_attributes))

        return list(self._devices_cache.values())

    def get(self, device_id: str, hass: HomeAssistant = None, raw_attributes: dict = None) -> dict:
        if raw_attributes is None:
            return self._devices_cache.get(device_id)
       
        device_name = raw_attributes.get(ATTR_DEVICE_NAME)
        device_type = None
        zone = None
        device_type = raw_attributes.get(ATTR_DEVICE_TYPE)
        # zone = raw_attributes.get(ATTR_DEVICE_ZONE)
        entity_ids = self.get_device_related_entities(hass, raw_attributes, device_type)
        actions = []
        properties = []

        for entity_id in entity_ids:
            device_name = self.get_device_name(hass, entity_id, raw_attributes, self._places, self._device_name_constraints) if device_name is None else device_name
            device_type = self.get_device_type(hass, entity_id, raw_attributes, device_name) if device_type is None else device_type
            zone = self.get_device_zone(hass, entity_id, raw_attributes, self._places, self._zone_constraints) if zone is None else zone
            properties += self.get_device_properties(hass, entity_id, raw_attributes)         
            actions += self.get_device_actions(hass, entity_id, raw_attributes, device_type)

        actions = list(set(actions))            
        # properties = list(set(properties))
            
        attributes = {
            ATTR_DEVICE_ID: device_id,
            ATTR_DEVICE_ENTITY_ID: entity_ids,
            ATTR_DEVICE_TYPE: device_type,
            ATTR_DEVICE_NAME: device_name,
            ATTR_DEVICE_ZONE: zone,
            ATTR_DEVICE_PROPERTIES: properties,
            ATTR_DEVICE_ACTIONS: actions
        }
        device = VoiceControllDevice(hass, self._entry, attributes, raw_attributes)
        return {device_id: device}

    def get_entity_related_device_ids(self, hass, entity_id):
        ids = []
        for vc_device in self.all(hass):
            if entity_id in vc_device.entity_id:
                ids.append(vc_device.device_id)
        return ids

    async def async_reregister_devices(self, hass = None):
        # entity_registry = await hass.helpers.entity_registry.async_get_registry()
        device_registry = await hass.helpers.device_registry.async_get_registry()
        device_registry.async_clear_config_entry(self._entry.entry_id)
        for device in self._devices_cache.values():
            await device.async_update_device_registry()
            # entity_ids = device.entity_id
            # for entity_id in entity_ids:
            #     entity = entity_registry.async_get(entity_id)
            #     entity_registry._async_update_entity(entity_id, device_id=device.device_id)

    def get_device_attrs(self, device_attributes) -> list:
        return device_attributes.get(ATTR_DEVICE_ID),device_attributes.get(ATTR_DEVICE_TYPE),device_attributes.get(ATTR_DEVICE_NAME),device_attributes.get(ATTR_DEVICE_ZONE),device_attributes.get(ATTR_DEVICE_PROPERTIES),device_attributes.get(ATTR_DEVICE_ACTIONS)

    def get_device_related_entities(self, hass, raw_attributes: dict, device_type: str = None) -> list:
        entity_ids = []
        for entity_id in raw_attributes.get(ATTR_DEVICE_ENTITY_ID, []):
            if entity_id.startswith('group.'):
                for entity_in_group_id in hass.states.get(entity_id).attributes.get(ATTR_DEVICE_ENTITY_ID):
                    if device_type is None or entity_in_group_id.startswith(device_type+'.'):
                        entity_ids.append(entity_in_group_id)
            else:
                entity_ids.append(entity_id)
        return entity_ids

    def get_device_type(self, hass, entity_id, raw_attributes, device_name) -> str:
        device_type = None

        if ATTR_DEVICE_TYPE in raw_attributes:
            device_type = self.device_type_map_h2p.get(raw_attributes[ATTR_DEVICE_TYPE])
            if device_type:
                return device_type

        # Guess from havcs_device_name
        if device_name:
            for device_type, alias in self._device_type_alias.items():
                if alias in device_name:
                    return device_type

        # Guess from entity's friendlyname
        state = hass.states.get(entity_id)
        if state:
            for device_type, alias in self._device_type_alias.items():
                if alias in state.attributes.get('friendly_name'):
                    return device_type

        # Guess from device_id
        for device_type in self._device_type_alias.keys():
            if device_type.lower() in entity_id:
                return device_type

        # Guess from device_id's domain
        device_type = entity_id[:entity_id.find('.')]
        # device_type = self.device_type_map_h2p.get(entity_id[:entity_id.find('.')])

        return device_type

    def get_device_name(self, hass, entity_id, raw_attributes = {}, places = [], device_name_constraints = []) -> str:
        device_name = None
        probably_device_names = []

        if ATTR_DEVICE_NAME in raw_attributes:
            device_name = raw_attributes[ATTR_DEVICE_NAME]
        else:
            # Guess from friendly_name
            state = hass.states.get(entity_id)
            if state:
                device_name = state.attributes.get('friendly_name')

        if device_name_constraints and device_name:
            # Name validation
            for device_name_constraint in device_name_constraints:
                aliases = [device_name_constraint['key']]+ device_name_constraint['value']
                aliases.reverse()
                for alias in aliases:
                    if alias in device_name:
                        probably_device_names += [alias]
            return max(probably_device_names) if probably_device_names else None
            
        return device_name

    def get_device_zone(self, hass, entity_id, raw_attributes, places = [], zone_constraints = []) ->str:
        zone = '未指定'
        if ATTR_DEVICE_ZONE in raw_attributes:
            zone = raw_attributes[ATTR_DEVICE_ZONE]
        else:
            device_name = raw_attributes.get(ATTR_DEVICE_NAME)
            # Guess from friendly_name
            state = hass.states.get(entity_id)
            if not device_name and state:
                device_name = state.attributes.get('friendly_name')

            if device_name:
                for place in places:
                    if  device_name.startswith(place):
                        zone = place
                        break
        if zone == '未指定':
            # Guess from HomeAssistant group which contains entity 
            for state in hass.states.async_all():
                group_entity_id = state.entity_id
                if group_entity_id.startswith('group.') and not group_entity_id.startswith('group.all_') and group_entity_id != 'group.default_view':
                    if entity_id in state.attributes.get(ATTR_DEVICE_ENTITY_ID):
                        for place in places:
                            if place in state.attributes.get('friendly_name'):
                                zone = place
                                break
        if zone_constraints:
            return zone if zone in zone_constraints else None
        else:
            return zone

    def get_device_properties(self, hass, entity_id, raw_attributes, attributes_constrains = []) -> list:
        properties = []
        if ATTR_DEVICE_ATTRIBUTES in raw_attributes:
            validated_property = self.get_device_properties(hass, entity_id, {}, raw_attributes[ATTR_DEVICE_ATTRIBUTES])
            if validated_property:
                properties += validated_property
        elif entity_id.startswith('sensor.'):
            state = hass.states.get(entity_id)
            if state is None:
                _LOGGER.debug("[%s] can not find sensor %s", LOGGER_NAME, entity_id)
                return []
            unit = state.attributes.get('unit_of_measurement', '')
            friendly_name = state.attributes.get('friendly_name', '')
            if unit == u'°C' or unit == u'℃' or 'temperature' in entity_id or '温度' in friendly_name :
                attribute = 'temperature'
            elif unit == 'lx' or unit == 'lm' or 'illumination' in entity_id or '光照' in friendly_name:
                attribute = 'illumination'
            elif 'humidity' in entity_id or  '湿度' in friendly_name:
                attribute = 'humidity'
            elif 'pm25' in entity_id or 'pm2.5' in friendly_name:
                attribute = 'pm25'
            elif 'co2' in entity_id or '二氧化碳' in friendly_name:
                attribute = 'co2'
            else:
                attribute = None
                _LOGGER.debug("[%s] unsupport sensor %s", LOGGER_NAME, entity_id)
            if not attributes_constrains or attribute in attributes_constrains:
                properties = [{'entity_id': entity_id, 'attribute': attribute}]
        else:
            properties = [{'entity_id': entity_id, 'attribute': 'power_state'}]
        return properties
    
    def get_property_related_entity_id(self, attribute, properties):
        for device_property in properties:
            if attribute == device_property.get('attribute'):
                return device_property.get('entity_id')

    def format_property(self, hass, device_properties, format_template):
        formatted_property = copy.deepcopy(format_template)
        for key in formatted_property:
            if '%' in formatted_property[key]:
                attribute = formatted_property[key][1:]
                entity_id = self.get_property_related_entity_id(attribute, device_properties)
                formatted_property[key] = hass.states.get(entity_id).state
        return formatted_property

    def get_device_actions(self, hass, entity_id, raw_attributes, device_type) -> list:
        if ATTR_DEVICE_ACTIONS in raw_attributes and raw_attributes[ATTR_DEVICE_ACTIONS]:
            # actions = [HAVCS_ACTIONS_ALIAS[DOMAIN].get(action) for action in raw_attributes[ATTR_DEVICE_ACTIONS].keys() if HAVCS_ACTIONS_ALIAS[DOMAIN].get(action)]
            actions = raw_attributes[ATTR_DEVICE_ACTIONS]
            if isinstance(actions, str):
                actions = [actions]
            elif isinstance(actions, dict):
                actions = actions.keys()
        elif device_type == 'switch':
            actions = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off"]
        elif device_type == 'light':
            actions = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off", "set_brightness", "increase_brightness", "decrease_brightness", "set_color"]
        elif device_type == 'cover':
            actions = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off", "pause"]
        elif device_type == 'vacuum':
            actions = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off"]
        elif device_type == 'sensor':
            actions = self.get_sensor_actions_from_properties(self.get_device_properties(hass, entity_id, raw_attributes))  
        elif entity_id.startswith('switch.'):
            actions = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off"]
        elif entity_id.startswith('light.'):
            actions = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off", "set_brightness", "increase_brightness", "decrease_brightness", "set_color"]
        elif entity_id.startswith('cover.'):
            actions = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off", "pause"]
        elif entity_id.startswith('vacuum.'):
            actions = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off"]
        elif entity_id.startswith('sensor.'):
            actions = self.get_sensor_actions_from_properties(self.get_device_properties(hass, entity_id, raw_attributes))  
        else:
            actions = ["turn_on", "turn_off", "timing_turn_on", "timing_turn_off"]
        return actions
    
    def get_sensor_actions_from_properties(self, properties) -> list:
        return [ 'query_' + device_property.get('attribute') for device_property in properties]
    
