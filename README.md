# 插件说明
对目前智能音箱接入插件进行了整合，其中天猫精灵和小度音箱插件基于瀚思彼岸论坛中小修改，叮咚音箱插件参考前两个插件编写。
本插件有三种使用模式：
1.http网关，适合有公网ip自建测试技能接入

2.http网关+mqtt中转，适合有无公网ip自建测试技能接入

3.mqtt，技能接入，目前技能暂未上线

# 配置说明（configuration.yaml）
```yaml
#{HA配置目录}/configuration.yaml
aihome:
  platform:
    - aligenie                    # 天猫精灵支持
    - dueros                      # 小度音箱支持
    - jdwhale                     # 叮咚音箱支持
  http:                           # 音箱插件http服务，自建测试技能接入用，否则可以删除
    expire_in_hours: 24             # token超时时间
  mqtt:                           # 音箱技能
    broker: mqtt.ljr.im             # MQTT服务器域名，默认即可
    port: 28883                     # MQTT服务器端口，默认即可
    app_key: xxx                    # 注册账号的用户名
    app_secret: xxx                 # 注册账号的密码
    certificate: xxx\custom_components\aihome\ca.crt             # 需要填插件内ca.crt的全路径
    tls_insecure: true              # 默认
    allowed_uri:                    # 自建测试技能接入有效
      - /auth/token
      - /dueros_gate
      - /aligenie_gate
      - /jdwhale_gate
     
```

# 更新日志
HA 0.86.4 和 HA 0.82.1，本地单机测试。
