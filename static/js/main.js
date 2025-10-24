/**
 * 主應用入口文件
 * 負責初始化所有模塊和協調組件
 */

// 導入配置
import { AppConfig } from './config/app.config.js';

// 導入核心模塊
import { WebSocketManager } from './core/WebSocketManager.js';
import { EventBus } from './core/EventBus.js';
import { StateManager, globalState } from './core/StateManager.js';

// 導入服務
import { apiService } from './services/ApiService.js';
import { historyService } from './services/HistoryService.js';
import { transcriptionService } from './services/TranscriptionService.js';

// 導入組件
import { notificationSystem } from './components/NotificationSystem.js';
import { loadingStateManager } from './components/LoadingStateManager.js';

// 導入控制器
import { transcriptionController } from './controllers/TranscriptionController.js';
import { historyController } from './controllers/HistoryController.js';
import { maintenanceController } from './controllers/MaintenanceController.js';

// 導入工具
import * as formatters from './utils/formatters.js';
import * as validators from './utils/validators.js';

/**
 * 主應用類
 */
class App {
    constructor() {
        this.clientId = this.generateClientId();
        this.websocket = null;
        this.eventBus = new EventBus();
        this.state = globalState;
        this.isInitialized = false;
    }

    /**
     * 生成客戶端 ID
     * @returns {string} - 客戶端 ID
     */
    generateClientId() {
        return Math.random().toString(36).substring(2, 15);
    }

    /**
     * 初始化應用
     */
    async init() {
        if (this.isInitialized) {
            console.warn('應用已經初始化');
            return;
        }

        console.log('應用初始化中...');
        console.log('客戶端 ID:', this.clientId);

        // 設置全局狀態
        this.state.set('clientId', this.clientId);

        // 初始化 WebSocket
        this.initWebSocket();

        // 設置事件監聽器
        this.setupEventListeners();

        this.isInitialized = true;
        console.log('✅ 應用初始化完成');

        // 顯示重構通知
        this.showRefactoringNotice();
    }

    /**
     * 初始化 WebSocket
     */
    initWebSocket() {
        this.websocket = new WebSocketManager(this.clientId, {
            reconnectInterval: AppConfig.websocket.reconnectInterval,
            heartbeatInterval: AppConfig.websocket.heartbeatInterval
        });

        // 註冊 WebSocket 訊息處理器
        this.websocket.on('progress', (data) => {
            this.handleProgressUpdate(data);
        });

        this.websocket.on('segment', (data) => {
            this.handleSegmentUpdate(data);
        });

        this.websocket.on('diarization_complete', (data) => {
            this.handleDiarizationComplete(data);
        });

        this.websocket.on('srt_complete', (data) => {
            this.handleSrtComplete(data);
        });

        // 連接 WebSocket
        this.websocket.connect();
    }

    /**
     * 處理進度更新
     * @param {Object} data - 進度數據
     */
    handleProgressUpdate(data) {
        const { progress } = data;
        const taskId = this.state.get('currentTask');

        // 更新轉錄控制器的進度
        if (transcriptionController && transcriptionController.updateProgress) {
            transcriptionController.updateProgress(progress);
        }

        if (taskId) {
            loadingStateManager.updateProgress(
                taskId,
                progress,
                `轉錄進度: ${progress}%`,
                'transcribing'
            );
        }
    }

    /**
     * 處理分段更新
     * @param {Object} data - 分段數據
     */
    handleSegmentUpdate(data) {
        console.log('收到新分段:', data);

        // 調用 TranscriptionController 的即時顯示方法
        if (transcriptionController && transcriptionController.addSegmentRealtime) {
            transcriptionController.addSegmentRealtime(data);
        }

        // 發送事件給其他監聽器
        this.eventBus.emit('segment:new', data);
    }

    /**
     * 處理說話者分離完成
     * @param {Object} data - 分段數據
     */
    handleDiarizationComplete(data) {
        console.log('說話者分離完成:', data);
        this.eventBus.emit('diarization:complete', data);
    }

    /**
     * 處理 SRT 完成
     * @param {Object} data - SRT 數據
     */
    handleSrtComplete(data) {
        console.log('SRT 文件完成:', data);
        this.eventBus.emit('srt:complete', data);
        notificationSystem.showSuccess('完成', 'SRT 字幕文件已生成');
    }

    /**
     * 設置事件監聽器
     */
    setupEventListeners() {
        // 監聽狀態變化
        this.state.watch('isLoading', (newValue, oldValue) => {
            console.log('載入狀態變化:', oldValue, '->', newValue);
        });

        // 監聽 DOM 載入完成
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.onDOMReady();
            });
        } else {
            this.onDOMReady();
        }
    }

    /**
     * DOM 就緒後執行
     */
    onDOMReady() {
        console.log('DOM 已就緒');
        // 初始化 UI 組件
        this.initUIComponents();
    }

    /**
     * 初始化 UI 組件
     */
    initUIComponents() {
        // 通知系統已自動初始化
        // 載入狀態管理器已自動初始化

        // 初始化所有控制器
        try {
            transcriptionController.init();
            historyController.init();
            maintenanceController.init();

            console.log('✅ UI 組件初始化完成');
        } catch (error) {
            console.error('❌ UI 組件初始化失敗:', error);
            notificationSystem.showError('初始化錯誤', 'UI 組件初始化失敗');
        }
    }

    /**
     * 顯示重構通知
     */
    showRefactoringNotice() {
        const container = document.querySelector('.container');

        if (!container) {
            return;
        }

        // 檢查是否已經顯示過通知
        if (document.getElementById('refactoring-notice')) {
            return;
        }

        const notice = document.createElement('div');
        notice.id = 'refactoring-notice';
        notice.className = 'bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded relative mb-4';
        notice.innerHTML = `
            <strong class="font-bold">前端重構進行中！</strong>
            <span class="block sm:inline">前端已完成模塊化重構。</span>
            <p class="mt-2 text-sm">
                ✅ CSS 模塊化已完成（6 個文件）<br>
                ✅ JavaScript 模塊化已完成（核心模塊、服務層、組件）<br>
                📦 使用 ES6 模塊系統，提升可維護性
            </p>
            <button class="absolute top-0 bottom-0 right-0 px-4 py-3" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;

        container.insertBefore(notice, container.firstChild);
    }

    /**
     * 銷毀應用
     */
    destroy() {
        if (this.websocket) {
            this.websocket.close();
        }

        if (this.eventBus) {
            this.eventBus.clear();
        }

        if (this.state) {
            this.state.destroy();
        }

        notificationSystem.destroy();
        loadingStateManager.destroy();

        this.isInitialized = false;
        console.log('應用已銷毀');
    }
}

// 創建全局應用實例
const app = new App();

// 將服務和組件綁定到全局（方便調試和使用）
window.app = app;
window.apiService = apiService;
window.historyService = historyService;
window.transcriptionService = transcriptionService;
window.notificationSystem = notificationSystem;
window.loadingStateManager = loadingStateManager;
window.transcriptionController = transcriptionController;
window.historyController = historyController;
window.maintenanceController = maintenanceController;
window.formatters = formatters;
window.validators = validators;

// 初始化應用
app.init().catch(error => {
    console.error('應用初始化失敗:', error);
    notificationSystem.showError('初始化失敗', error.message);
});

// 預設匯出
export default app;
