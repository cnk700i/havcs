# 备注
插件使用有点复杂，有疑问请加QQ群307773400交流。
# 插件说明
对目前智能音箱接入插件进行了整合，其中天猫精灵和小度音箱插件基于瀚思彼岸论坛[@feversky](https://bbs.hassbian.com/thread-4758-1-1.html)和[@zhkufish](https://bbs.hassbian.com/thread-5417-1-1.html)插件进行小修改，叮咚音箱插件参考前两个插件编写。
本插件有三种使用模式：

1. http网关，适合有公网ip自建测试技能接入
> 传统接入方法

2. http网关+mqtt中转，适合有无公网ip自建测试技能接入
> 原先本人[http2mqtt2hass](https://github.com/cnk700i/http2mqtt2hass)插件接入方法

3. mqtt，技能接入，目前技能暂未上线
> 原先计划采用自[定义技能方式接入](https://ljr.im/2019/01/20/aihomesmart-speaker-universal-access-platform/)，因翻车改用智能家居技能对接
# 配置说明（configuration.yaml）
```yaml
#{HA配置目录}/configuration.yaml
aihome:
  platform:                         # 加载内置智能音箱插件服务
    # - aligenie                        # 天猫精灵
    # - dueros                          # 小度
    - jdwhale                         # 叮咚
  http:                             # 启用http网关功能（模式一、模式二需设置）
    expire_in_hours: 24               # token超时时间，单位小时，不设置则默认24h
  mqtt:                             # 启用mqtt对接功能（模式二、模式三需设置）
    broker: mqtt.ljr.im               # MQTT服务器域名，不设置则默认为mqtt.ljr.im
    port: 28883                       # MQTT服务器端口，不设置则默认为28883
    app_key: xxx                      # 必填，https://ai-home.ljr.im/account/获取
    app_secret: xxx                   # 必填，https://ai-home.ljr.im/account/获取
    entity_key: xxx                   # 必填，加密entity_id的key，自由设置16位字符串
    certificate: xxx/ca.crt           # 必填，插件内ca.crt文件完整路径
    tls_insecure: true                # 必填，不校验证书主机名，因为ca.crt是自签证书，设置true
    ha_url: https://localhost:8123    # 本地HA访问网址，不设置则默认为http://localhost:8123
    allowed_uri:                      # http请求白名单，不设置则默认不限制（模式一、模式二才有效）
      - /auth/token
      - /dueros_gate
      - /aligenie_gate
      - /jdwhale_gate
     
```
# 设备配置
待施工

# 更新日志
HA 0.86.4 和 HA 0.82.1，本地单机测试。
