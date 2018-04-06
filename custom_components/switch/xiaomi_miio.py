"""
Support for Xiaomi Smart WiFi Socket and Smart Power Strip.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/switch.xiaomi_miio/
"""
import asyncio
from functools import partial
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA,
                                             DOMAIN, )
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_TOKEN,
                                 ATTR_ENTITY_ID)
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Miio Switch'
PLATFORM = 'xiaomi_miio'

CONF_MODEL = 'model'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MODEL, default=None): vol.In(
        ['chuangmi.plug.v1',
         'qmi.powerstrip.v1',
         'zimi.powerstrip.v2',
         'chuangmi.plug.m1',
         'chuangmi.plug.v2', None]),

})

REQUIREMENTS = ['python-miio>=0.3.5']

ATTR_POWER = 'power'
ATTR_TEMPERATURE = 'temperature'
ATTR_LOAD_POWER = 'load_power'
ATTR_MODEL = 'model'
ATTR_MODE = 'mode'
SUCCESS = ['ok']

SUPPORT_SET_POWER_MODE = 1

SERVICE_SET_POWER_MODE = 'xiaomi_miio_set_power_mode'

SERVICE_SCHEMA_POWER_MODE = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_MODE): vol.All(vol.In(['green', 'normal'])),
})

# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the switch from config."""
    from miio import Device, DeviceException
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    model = config.get(CONF_MODEL)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    devices = []

    if model is None:
        try:
            miio_device = Device(host, token)
            device_info = miio_device.info()
            model = device_info.model
            _LOGGER.info("%s %s %s detected",
                         model,
                         device_info.firmware_version,
                         device_info.hardware_version)
        except DeviceException:
            raise PlatformNotReady

    if model in ['chuangmi.plug.v1']:
        from miio import PlugV1
        plug = PlugV1(host, token)

        # The device has two switchable channels (mains and a USB port).
        # A switch device per channel will be created.
        for channel_usb in [True, False]:
            device = ChuangMiPlugV1Switch(
                name, plug, model, channel_usb)
            devices.append(device)
            hass.data[PLATFORM][host] = device

    elif model in ['qmi.powerstrip.v1',
                   'zimi.powerstrip.v2']:
        from miio import PowerStrip
        plug = PowerStrip(host, token)
        device = XiaomiPowerStripSwitch(name, plug, model)
        devices.append(device)
        hass.data[PLATFORM][host] = device
    elif model in ['chuangmi.plug.m1',
                   'chuangmi.plug.v2']:
        from miio import Plug
        plug = Plug(host, token)
        device = XiaomiPlugGenericSwitch(name, plug, model)
        devices.append(device)
        hass.data[PLATFORM][host] = device
    else:
        _LOGGER.error(
            'Unsupported device found! Please create an issue at '
            'https://github.com/rytilahti/python-miio/issues '
            'and provide the following data: %s', model)
        return False

    async_add_devices(devices, update_before_add=True)

    @asyncio.coroutine
    def async_service_handler(service):
        """Map services to methods on XiaomiPlugGenericSwitch."""
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [device for device in hass.data[PLATFORM].values() if
                       device.entity_id in entity_ids]
        else:
            devices = hass.data[PLATFORM].values()

        update_tasks = []
        for device in devices:
            yield from getattr(device, 'async_set_power_mode')(**params)
            update_tasks.append(device.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_POWER_MODE, async_service_handler,
        schema=SERVICE_SCHEMA_POWER_MODE)


class XiaomiPlugGenericSwitch(SwitchDevice):
    """Representation of a Xiaomi Plug Generic."""

    def __init__(self, name, plug, model):
        """Initialize the plug switch."""
        self._name = name
        self._icon = 'mdi:power-socket'
        self._model = model

        self._plug = plug
        self._state = None
        self._state_attrs = {
            ATTR_TEMPERATURE: None,
            ATTR_MODEL: self._model,
        }
        self._skip_update = False

    @property
    def supported_features(self):
        """Flag supported features."""
        return 0

    @property
    def should_poll(self):
        """Poll the plug."""
        return True

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._state is not None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @asyncio.coroutine
    def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a plug command handling error messages."""
        from miio import DeviceException
        try:
            result = yield from self.hass.async_add_job(
                partial(func, *args, **kwargs))

            _LOGGER.debug("Response received from plug: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the plug on."""
        result = yield from self._try_command(
            "Turning the plug on failed.", self._plug.on)

        if result:
            self._state = True
            self._skip_update = True

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the plug off."""
        result = yield from self._try_command(
            "Turning the plug off failed.", self._plug.off)

        if result:
            self._state = False
            self._skip_update = True

    @asyncio.coroutine
    def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = yield from self.hass.async_add_job(self._plug.status)
            _LOGGER.debug("Got new state: %s", state)

            self._state = state.is_on
            self._state_attrs.update({
                ATTR_TEMPERATURE: state.temperature
            })

        except DeviceException as ex:
            self._state = None
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    @asyncio.coroutine
    def async_set_power_mode(self, mode: str):
        """Set the power mode."""
        return


class XiaomiPowerStripSwitch(XiaomiPlugGenericSwitch, SwitchDevice):
    """Representation of a Xiaomi Power Strip."""

    def __init__(self, name, plug, model):
        """Initialize the plug switch."""
        XiaomiPlugGenericSwitch.__init__(self, name, plug, model)

        self._state_attrs.update({
            ATTR_LOAD_POWER: None,
        })

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SET_POWER_MODE

    @asyncio.coroutine
    def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = yield from self.hass.async_add_job(self._plug.status)
            _LOGGER.debug("Got new state: %s", state)

            self._state = state.is_on
            self._state_attrs.update({
                ATTR_TEMPERATURE: state.temperature,
                ATTR_LOAD_POWER: state.load_power
            })

        except DeviceException as ex:
            self._state = None
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    @asyncio.coroutine
    def async_set_power_mode(self, mode: str):
        """Set the power mode."""
        if self.supported_features & SUPPORT_SET_POWER_MODE == 0:
            return

        from miio.powerstrip import PowerMode

        yield from self._try_command(
            "Setting the power mode of the power strip failed.",
            self._plug.set_power_mode, PowerMode(mode))


class ChuangMiPlugV1Switch(XiaomiPlugGenericSwitch, SwitchDevice):
    """Representation of a Chuang Mi Plug V1."""

    def __init__(self, name, plug, model, channel_usb):
        """Initialize the plug switch."""
        name = name + ' USB' if channel_usb else name

        XiaomiPlugGenericSwitch.__init__(self, name, plug, model)
        self._channel_usb = channel_usb

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn a channel on."""
        if self._channel_usb:
            result = yield from self._try_command(
                "Turning the plug on failed.", self._plug.usb_on)
        else:
            result = yield from self._try_command(
                "Turning the plug on failed.", self._plug.on)

        if result:
            self._state = True
            self._skip_update = True

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn a channel off."""
        if self._channel_usb:
            result = yield from self._try_command(
                "Turning the plug on failed.", self._plug.usb_off)
        else:
            result = yield from self._try_command(
                "Turning the plug on failed.", self._plug.off)

        if result:
            self._state = False
            self._skip_update = True

    @asyncio.coroutine
    def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = yield from self.hass.async_add_job(self._plug.status)
            _LOGGER.debug("Got new state: %s", state)

            if self._channel_usb:
                self._state = state.usb_power
            else:
                self._state = state.is_on

            self._state_attrs.update({
                ATTR_TEMPERATURE: state.temperature
            })

        except DeviceException as ex:
            self._state = None
            _LOGGER.error("Got exception while fetching the state: %s", ex)
