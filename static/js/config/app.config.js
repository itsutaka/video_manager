/**
 * 應用配置文件
 * 集中管理所有配置常量
 */

export const AppConfig = {
    // API 端點
    api: {
        base: window.location.origin,
        transcription: '/v1/audio/transcriptions',
        history: '/api/history',
        maintenance: '/api/maintenance',
        websocket: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`
    },

    // WebSocket 設定
    websocket: {
        reconnectInterval: 3000,
        heartbeatInterval: 30000
    },

    // 分頁設定
    pagination: {
        defaultPageSize: 10,
        maxPageSize: 100
    },

    // 檔案大小限制
    upload: {
        maxFileSize: 500 * 1024 * 1024, // 500MB
        allowedExtensions: ['.mp3', '.wav', '.m4a', '.flac', '.ogg']
    },

    // 通知設定
    notification: {
        defaultDuration: 5000,
        successDuration: 3000,
        errorDuration: 8000
    },

    // 快取設定
    cache: {
        ttl: 5 * 60 * 1000, // 5 分鐘
        maxSize: 100
    }
};
