class HA {
    constructor() {
        // url参数
        let query = new URLSearchParams(location.search)
        this.query = (key) => {
            let val = query.get(key)
            if (val) {
                return decodeURIComponent(val)
            }
            return val
        }
        this.ver = this.query('ver')
    }

    fullscreen() {
        try {
            let haPanelIframe = top.document.body
                .querySelector("home-assistant")
                .shadowRoot.querySelector("home-assistant-main")
                .shadowRoot.querySelector("app-drawer-layout partial-panel-resolver ha-panel-iframe").shadowRoot
            let ha_card = haPanelIframe.querySelector("iframe");
            ha_card.style.position = 'absolute'
            haPanelIframe.querySelector('app-toolbar').style.display = 'none'
            ha_card.style.top = '0'
            ha_card.style.height = '100%'
        } catch{

        }
    }

    // 触发事件
    fire(type, data, ele = null) {
        console.log(type, data)
        const event = new top.Event(type, {
            bubbles: true,
            cancelable: false,
            composed: true
        });
        event.detail = data;
        if (!ele) {
            ele = top.document.querySelector("home-assistant")
                .shadowRoot.querySelector("home-assistant-main")
                .shadowRoot.querySelector("app-drawer-layout")
        }
        ele.dispatchEvent(event);
    }
    async getAuthorization(){
        let hass = top.document.querySelector('home-assistant').hass
        let auth = hass.auth
        let authorization = ''
        if (auth._saveTokens) {
            // 过期
            if (auth.expired) {
                await auth.refreshAccessToken()
            }
            authorization = `${auth.data.token_type} ${auth.accessToken}`
        } else {
            authorization = `Bearer ${auth.data.access_token}`
        }
        return authorization
    }

    async post(params) {
        let data
        if(params instanceof FormData){
            data = params
        }else if(params instanceof Object){
            data = JSON.stringify(params)
        }else{
            data = params
        }
        let url = '/havcs/device'
        let authorization = await this.getAuthorization()
        return fetch(url, {
            method: 'post',
            headers: {
                authorization
            },
            body: data
        }).then(res => res.json())
    }

    async file(params) {
        let url = '/havcs/device'
        let authorization = await this.getAuthorization()

        fetch(url, {
            method: 'post',
            headers: {
                authorization
            },
            body: JSON.stringify(params)
        }).then(res => res.blob().then(blob => {
                // It is necessary to create a new blob object with mime-type explicitly set
                // otherwise only Chrome works like it should
                var newBlob = new Blob([blob], {type: "application/x-yaml"})
                console.log(res.headers)
                console.log(res.headers.get('Content-Type'))
                // IE doesn't allow using a blob object directly as link href
                // instead it is necessary to use msSaveOrOpenBlob
                if (window.navigator && window.navigator.msSaveOrOpenBlob) {
                    window.navigator.msSaveOrOpenBlob(newBlob);
                    return;
                }
                // For other browsers:
                // Create a link pointing to the ObjectURL containing the blob.

                var a = document.createElement('a'); 
                var url = window.URL.createObjectURL(newBlob);   // 获取 blob 本地文件连接 (blob 为纯二进制对象，不能够直接保存到磁盘上)
                var filename = res.headers.get('Content-Disposition'); 
                a.href = url; 
                a.download = filename; 
                a.click(); 
                setTimeout(function(){
                    // For Firefox it is necessary to delay revoking the ObjectURL
                    window.URL.revokeObjectURL(url);
                }, 100);
        }));
    }
}

window.ha = new HA()