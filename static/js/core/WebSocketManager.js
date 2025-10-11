/**
 * WebSocket 管理器
 * 負責 WebSocket 連接管理、訊息處理和自動重連
 */

export class WebSocketManager {
    constructor(clientId, config = {}) {
        this.clientId = clientId;
        this.socket = null;
        this.reconnectInterval = config.reconnectInterval || 3000;
        this.heartbeatInterval = config.heartbeatInterval || 30000;
        this.heartbeatTimer = null;
        this.messageHandlers = new Map();
        this.isConnected = false;
    }

    /**
     * 初始化 WebSocket 連接
     */
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.clientId}`;

        console.log('正在建立 WebSocket 連接:', wsUrl);

        this.socket = new WebSocket(wsUrl);

        // 連接建立成功
        this.socket.onopen = () => {
            console.log('WebSocket 連接已建立');
            this.isConnected = true;
            this.startHeartbeat();
            this.emit('open');
        };

        // 接收訊息
        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('收到 WebSocket 訊息:', data);
                this.handleMessage(data);
            } catch (error) {
                console.error('解析 WebSocket 訊息錯誤:', error, event.data);
            }
        };

        // 連接錯誤
        this.socket.onerror = (error) => {
            console.error('WebSocket 錯誤:', error);
            this.isConnected = false;
            this.emit('error', error);
        };

        // 連接關閉
        this.socket.onclose = (event) => {
            console.log('WebSocket 連接已關閉:', event.code, event.reason);
            this.isConnected = false;
            this.stopHeartbeat();
            this.emit('close', event);

            // 自動重新連接
            setTimeout(() => {
                console.log('嘗試重新連接 WebSocket...');
                this.connect();
            }, this.reconnectInterval);
        };
    }

    /**
     * 處理接收到的訊息
     */
    handleMessage(data) {
        const { type } = data;

        // 觸發特定類型的處理器
        if (this.messageHandlers.has(type)) {
            const handlers = this.messageHandlers.get(type);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`處理 ${type} 訊息時發生錯誤:`, error);
                }
            });
        }

        // 觸發通用訊息處理器
        this.emit('message', data);
    }

    /**
     * 註冊訊息處理器
     * @param {string} type - 訊息類型
     * @param {Function} handler - 處理函數
     */
    on(type, handler) {
        if (!this.messageHandlers.has(type)) {
            this.messageHandlers.set(type, []);
        }
        this.messageHandlers.get(type).push(handler);
    }

    /**
     * 移除訊息處理器
     * @param {string} type - 訊息類型
     * @param {Function} handler - 處理函數
     */
    off(type, handler) {
        if (this.messageHandlers.has(type)) {
            const handlers = this.messageHandlers.get(type);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }

    /**
     * 發送訊息到伺服器
     * @param {Object} data - 要發送的資料
     */
    send(data) {
        if (this.isConnected && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket 未連接，無法發送訊息');
        }
    }

    /**
     * 觸發事件
     * @param {string} event - 事件名稱
     * @param {*} data - 事件資料
     */
    emit(event, data) {
        const customEvent = new CustomEvent(`websocket:${event}`, { detail: data });
        window.dispatchEvent(customEvent);
    }

    /**
     * 啟動心跳檢測
     */
    startHeartbeat() {
        this.stopHeartbeat(); // 清除舊的定時器

        this.heartbeatTimer = setInterval(() => {
            if (this.isConnected) {
                this.send({ type: 'ping', timestamp: Date.now() });
            }
        }, this.heartbeatInterval);
    }

    /**
     * 停止心跳檢測
     */
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    /**
     * 關閉 WebSocket 連接
     */
    close() {
        this.stopHeartbeat();
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.isConnected = false;
        this.messageHandlers.clear();
    }

    /**
     * 獲取連接狀態
     */
    getState() {
        if (!this.socket) return 'CLOSED';

        switch (this.socket.readyState) {
            case WebSocket.CONNECTING:
                return 'CONNECTING';
            case WebSocket.OPEN:
                return 'OPEN';
            case WebSocket.CLOSING:
                return 'CLOSING';
            case WebSocket.CLOSED:
                return 'CLOSED';
            default:
                return 'UNKNOWN';
        }
    }
}

// 預設匯出
export default WebSocketManager;
