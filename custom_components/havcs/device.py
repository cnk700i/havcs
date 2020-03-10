DOMAIN = 'havcs'

class VoiceControllDevice:

    def __init__(self, hass, config_entry, attributes, raw_attributes):
        """Initialize the device."""
        self.hass = hass
        self.config_entry = config_entry
        self._attributes = attributes
        self._raw_attributes = raw_attributes
        self.available = True
        self.sw_version='v3'
        self.product_type = None
        self._device_id = None

    @property
    def raw_attributes(self):
        return self._raw_attributes

    @property
    def attributes(self):
        return self._attributes

    @property
    def device_id(self):
        """Return the device_id of this device."""
        return self._device_id

    @property
    def entity_id(self):
        """Return the entity_ids of this device."""
        return self._attributes['entity_id']
    @property
    def properties(self):
        return self._attributes['properties']

    @property
    def model(self):
        """Return the model of this device."""
        return f"{self._attributes['device_id']} <-> {self._attributes['entity_id']}"

    @property
    def name(self):
        """Return the name of this device."""
        return self._attributes['name']

    @property
    def serial(self):
        """Return the serial number of this device."""
        return self._attributes['device_id']

    async def async_update_device_registry(self):
        """Update device registry."""
        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        device = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={('CONNECTION_NETWORK_MAC', self.serial)},
            identifiers={(DOMAIN, self.serial)},
            manufacturer="HAVCS",
            model=self.model,
            name=self.name,
            sw_version=self.sw_version,
        )
        self._device_id = device.id
    
    async def async_setup(self):
        
        return True