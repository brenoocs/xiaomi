# Xiaomi WiFi Plug

This is a custom component for Home Assistant to integrate the Xiaomi Smart WiFi Socket (called Plug), Xiaomi Smart Power Strip and Xiaomi Chuangmi Plug V1.

Please follow the instructions on [Retrieving the Access Token](https://home-assistant.io/components/xiaomi/#retrieving-the-access-token) to get the API token to use in the configuration.yaml file.

Credits: Thanks to [Rytilahti](https://github.com/rytilahti/python-miio) for all the work.

## Features
* On, Off
* USB on, off (Chuangmi Plug V1 only)
* Current state
* Attributes
  - Temperature
  - Load (Power Strip only)

# Setup

```
switch:
  - platform: xiaomi_miio
    name: Original Xiaomi Mi Smart WiFi Socket
    host: 192.168.130.59
    token: b7c4a758c251955d2c24b1d9e41ce47d
    model: chuangmi.plug.m1
  - platform: xiaomi_miio
    name: Xiaomi Mi Smart Power Strip
    host: 192.168.130.60
    token: 0ed0fdccb2d0cd718108f18a447726a6
    model: zimi.powerstrip.v2
```

Configuration variables:
- **host** (*Required*): The IP of your light.
- **token** (*Required*): The API token of your light.
- **name** (*Optional*): The name of your light.
- **model** (*Optional*): The model of your device. Valid values are `chuangmi.plug.v1`, `qmi.powerstrip.v1`, `zimi.powerstrip.v2`, `chuangmi.plug.m1` and `chuangmi.plug.v2`. This setting can be used to bypass the device model detection and is recommended if your device isn't always available.

## Platform services

#### Service switch/xiaomi_miio_set_power_mode (Power Strip only)

Set the power mode.

| Service data attribute    | Optional | Description                                                   |
|---------------------------|----------|---------------------------------------------------------------|
| `entity_id`               |      yes | Only act on a specific xiaomi miio entity. Else targets all.  |
| `mode`                    |       no | Power mode, valid values are 'normal' and 'green'             |
