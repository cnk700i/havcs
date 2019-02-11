# 配置说明（configuration.yaml）
```yaml
#{HA配置目录}/configuration.yaml
aihome:
  platform:
    - aligenie                    # 天猫精灵支持
    - dueros                      # 小度音箱支持
    - jdwhale                     # 叮咚音箱支持
  http:
    expire_in_hours: 24           # token超时时间
  mqtt:
    broker: mqtt.ljr.im           # MQTT服务器域名，默认即可
    port: 28883                   # MQTT服务器端口，默认即可
    app_key: xxx                  # 注册账号的用户名
    app_secret: xxx               # 注册账号的密码
    certificate: xxx\custom_components\aihome\ca.crt             # 需要填插件内ca.crt的全路径
    tls_insecure: true            # 默认
    allowed_uri:                  # 自建测试技能接入有效
      - /auth/token
      - /dueros_gate
      - /aligenie_gate
      - /jdwhale_gate
     
```

# 更新日志
HA 0.86.4 和 HA 0.82.1，天猫精灵和小度音箱通过测试。
