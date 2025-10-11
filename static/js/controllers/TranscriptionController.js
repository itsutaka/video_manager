/**
 * 轉錄控制器
 * 處理語音轉文字相關的 UI 事件和邏輯
 */

import { transcriptionService } from '../services/TranscriptionService.js';
import { notificationSystem } from '../components/NotificationSystem.js';
import { loadingStateManager } from '../components/LoadingStateManager.js';
import { globalState } from '../core/StateManager.js';

export class TranscriptionController {
    constructor() {
        this.currentFile = null;
        this.segments = [];
        this.isProcessing = false;

        this.elements = {
            // 檔案上傳相關
            fileInput: document.getElementById('fileInput'),
            dropzone: document.getElementById('dropzone'),
            fileInfo: document.getElementById('fileInfo'),
            fileName: document.getElementById('fileName'),
            fileSize: document.getElementById('fileSize'),
            removeFile: document.getElementById('removeFile'),

            // YouTube 相關
            youtubeUrl: document.getElementById('youtubeUrl'),
            clearYoutubeUrl: document.getElementById('clearYoutubeUrl'),

            // 配置選項
            language: document.getElementById('language'),
            withDiarization: document.getElementById('withDiarization'),
            vadEnabled: document.getElementById('vadEnabled'),
            vadSettings: document.getElementById('vadSettings'),
            vadInfoIcon: document.getElementById('vadInfoIcon'),
            vadTooltip: document.getElementById('vadTooltip'),
            minSilenceDuration: document.getElementById('minSilenceDuration'),
            speechPad: document.getElementById('speechPad'),
            downloadVideo: document.getElementById('downloadVideo'),
            downloadThumbnail: document.getElementById('downloadThumbnail'),

            // 按鈕
            transcribeBtn: document.getElementById('transcribeBtn'),
            downloadBtn: document.getElementById('downloadBtn'),
            copyBtn: document.getElementById('copyBtn'),
            exportBtn: document.getElementById('exportBtn'),
            exportDropdown: document.getElementById('exportDropdown'),
            exportTxtBtn: document.getElementById('exportTxtBtn'),
            exportSrtBtn: document.getElementById('exportSrtBtn'),

            // 結果顯示
            transcriptionContainer: document.getElementById('transcriptionContainer'),
            loadingIndicator: document.getElementById('loadingIndicator'),
            progressBar: document.getElementById('progressBar'),
            progressPercent: document.getElementById('progressPercent'),
            transcriptText: document.getElementById('transcriptText'),
            segmentsContainer: document.getElementById('segmentsContainer'),
            segmentsList: document.getElementById('segmentsList')
        };
    }

    /**
     * 初始化控制器
     */
    init() {
        this.bindEvents();
        console.log('✅ TranscriptionController 已初始化');
    }

    /**
     * 綁定所有事件
     */
    bindEvents() {
        // 檔案上傳事件
        if (this.elements.fileInput) {
            this.elements.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        }

        if (this.elements.dropzone) {
            this.elements.dropzone.addEventListener('dragover', (e) => this.handleDragOver(e));
            this.elements.dropzone.addEventListener('drop', (e) => this.handleDrop(e));
        }

        if (this.elements.removeFile) {
            this.elements.removeFile.addEventListener('click', () => this.removeFile());
        }

        // YouTube URL 事件
        if (this.elements.clearYoutubeUrl) {
            this.elements.clearYoutubeUrl.addEventListener('click', () => this.clearYoutubeUrl());
        }

        // VAD 設定事件
        if (this.elements.vadEnabled) {
            this.elements.vadEnabled.addEventListener('change', (e) => this.toggleVadSettings(e.target.checked));
        }

        if (this.elements.vadInfoIcon && this.elements.vadTooltip) {
            this.elements.vadInfoIcon.addEventListener('mouseenter', () => {
                this.elements.vadTooltip.classList.remove('hidden');
            });
            this.elements.vadInfoIcon.addEventListener('mouseleave', () => {
                this.elements.vadTooltip.classList.add('hidden');
            });
        }

        // 轉錄按鈕事件
        if (this.elements.transcribeBtn) {
            this.elements.transcribeBtn.addEventListener('click', () => this.handleTranscribe());
        }

        // 結果操作按鈕事件
        if (this.elements.copyBtn) {
            this.elements.copyBtn.addEventListener('click', () => this.copyTranscript());
        }

        if (this.elements.exportBtn) {
            this.elements.exportBtn.addEventListener('click', () => this.toggleExportDropdown());
        }

        if (this.elements.exportTxtBtn) {
            this.elements.exportTxtBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.exportTranscript('txt');
            });
        }

        if (this.elements.exportSrtBtn) {
            this.elements.exportSrtBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.exportTranscript('srt');
            });
        }

        // 點擊其他地方關閉下拉選單
        document.addEventListener('click', (e) => {
            if (this.elements.exportBtn && this.elements.exportDropdown &&
                !this.elements.exportBtn.contains(e.target)) {
                this.elements.exportDropdown.classList.add('hidden');
            }
        });
    }

    /**
     * 處理檔案選擇
     */
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.setFile(file);
        }
    }

    /**
     * 處理拖放
     */
    handleDragOver(event) {
        event.preventDefault();
        event.stopPropagation();
        this.elements.dropzone.classList.add('border-blue-500', 'bg-blue-50');
    }

    /**
     * 處理放下檔案
     */
    handleDrop(event) {
        event.preventDefault();
        event.stopPropagation();
        this.elements.dropzone.classList.remove('border-blue-500', 'bg-blue-50');

        const file = event.dataTransfer.files[0];
        if (file) {
            this.setFile(file);
        }
    }

    /**
     * 設定當前檔案
     */
    setFile(file) {
        this.currentFile = file;

        // 顯示檔案資訊
        this.elements.fileName.textContent = file.name;
        this.elements.fileSize.textContent = this.formatFileSize(file.size);
        this.elements.fileInfo.classList.remove('hidden');

        // 清除 YouTube URL
        if (this.elements.youtubeUrl) {
            this.elements.youtubeUrl.value = '';
        }
    }

    /**
     * 移除檔案
     */
    removeFile() {
        this.currentFile = null;
        this.elements.fileInput.value = '';
        this.elements.fileInfo.classList.add('hidden');
    }

    /**
     * 清除 YouTube URL
     */
    clearYoutubeUrl() {
        if (this.elements.youtubeUrl) {
            this.elements.youtubeUrl.value = '';
        }
    }

    /**
     * 切換 VAD 設定顯示
     */
    toggleVadSettings(enabled) {
        if (this.elements.vadSettings) {
            if (enabled) {
                this.elements.vadSettings.classList.remove('hidden');
            } else {
                this.elements.vadSettings.classList.add('hidden');
            }
        }
    }

    /**
     * 處理轉錄請求
     */
    async handleTranscribe() {
        if (this.isProcessing) {
            notificationSystem.showWarning('處理中', '正在處理中，請稍候');
            return;
        }

        // 獲取輸入
        const file = this.currentFile;
        const youtubeUrl = this.elements.youtubeUrl?.value.trim();

        if (!file && !youtubeUrl) {
            notificationSystem.showError('錯誤', '請上傳音頻文件或輸入 YouTube 連結');
            return;
        }

        // 準備轉錄選項
        const options = {
            file: file,
            youtubeUrl: youtubeUrl,
            language: this.elements.language?.value || '',
            withDiarization: this.elements.withDiarization?.checked || false,
            vadEnabled: this.elements.vadEnabled?.checked || false,
            vadSettings: {
                minSilenceDuration: parseInt(this.elements.minSilenceDuration?.value) || 500,
                speechPad: parseInt(this.elements.speechPad?.value) || 400
            },
            downloadVideo: this.elements.downloadVideo?.checked || false,
            downloadThumbnail: this.elements.downloadThumbnail?.checked || false,
            clientId: globalState.get('clientId')
        };

        try {
            this.isProcessing = true;
            this.segments = [];

            // 顯示載入狀態
            this.showLoading();

            // 提交轉錄任務
            const result = await transcriptionService.submit(options);

            console.log('轉錄結果:', result);

            // 處理結果
            if (result.text) {
                this.displayTranscript(result.text);
            }

            if (result.segments) {
                this.segments = result.segments;
                this.displaySegments(result.segments);
            }

            // 隱藏載入狀態
            this.hideLoading();

            // 顯示成功訊息
            notificationSystem.showSuccess('完成', '轉錄已完成');

        } catch (error) {
            console.error('轉錄失敗:', error);
            this.hideLoading();
            notificationSystem.showError('錯誤', error.message || '轉錄失敗');
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * 顯示載入狀態
     */
    showLoading() {
        if (this.elements.transcriptionContainer) {
            this.elements.transcriptionContainer.classList.remove('hidden');
        }
        if (this.elements.loadingIndicator) {
            this.elements.loadingIndicator.classList.remove('hidden');
        }
        if (this.elements.transcriptText) {
            this.elements.transcriptText.innerHTML = '';
        }
        if (this.elements.segmentsList) {
            this.elements.segmentsList.innerHTML = '';
        }

        // 更新進度為 0
        this.updateProgress(0);
    }

    /**
     * 隱藏載入狀態
     */
    hideLoading() {
        if (this.elements.loadingIndicator) {
            this.elements.loadingIndicator.classList.add('hidden');
        }
    }

    /**
     * 更新進度
     */
    updateProgress(progress) {
        if (this.elements.progressBar) {
            this.elements.progressBar.style.width = `${progress}%`;
        }
        if (this.elements.progressPercent) {
            this.elements.progressPercent.textContent = `${progress}%`;
        }
    }

    /**
     * 顯示轉錄文本
     */
    displayTranscript(text) {
        if (this.elements.transcriptText) {
            this.elements.transcriptText.textContent = text;
        }
    }

    /**
     * 顯示分段
     */
    displaySegments(segments) {
        if (!this.elements.segmentsList) return;

        this.elements.segmentsList.innerHTML = '';

        segments.forEach((segment, index) => {
            const segmentDiv = document.createElement('div');
            segmentDiv.className = 'p-4 bg-gray-50 rounded-lg border border-gray-200';

            let speakerBadge = '';
            if (segment.speaker) {
                const speakerClass = this.getSpeakerColorClass(segment.speaker);
                speakerBadge = `<span class="inline-block px-2 py-1 text-xs font-semibold rounded ${speakerClass} mr-2">${segment.speaker}</span>`;
            }

            const timeRange = transcriptionService.formatTimeRange(segment.start, segment.end);

            segmentDiv.innerHTML = `
                <div class="flex items-center justify-between mb-2">
                    <div class="flex items-center">
                        ${speakerBadge}
                        <span class="text-sm text-gray-500">${timeRange}</span>
                    </div>
                    <span class="text-xs text-gray-400">#${index + 1}</span>
                </div>
                <p class="text-gray-800">${segment.text}</p>
            `;

            this.elements.segmentsList.appendChild(segmentDiv);
        });
    }

    /**
     * 獲取說話者顏色類別
     */
    getSpeakerColorClass(speaker) {
        return transcriptionService.getSpeakerColorClass(speaker);
    }

    /**
     * 複製轉錄文本
     */
    async copyTranscript() {
        const text = this.elements.transcriptText?.textContent;
        if (!text) {
            notificationSystem.showWarning('提示', '沒有可複製的內容');
            return;
        }

        try {
            await navigator.clipboard.writeText(text);
            notificationSystem.showSuccess('成功', '已複製到剪貼簿');
        } catch (error) {
            console.error('複製失敗:', error);
            notificationSystem.showError('錯誤', '複製失敗');
        }
    }

    /**
     * 切換匯出下拉選單
     */
    toggleExportDropdown() {
        if (this.elements.exportDropdown) {
            this.elements.exportDropdown.classList.toggle('hidden');
        }
    }

    /**
     * 匯出轉錄文本
     */
    exportTranscript(format) {
        if (this.segments.length === 0) {
            notificationSystem.showWarning('提示', '沒有可匯出的內容');
            return;
        }

        const content = transcriptionService.exportTranscript(this.segments, format);
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `transcript_${Date.now()}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        notificationSystem.showSuccess('成功', `已匯出 ${format.toUpperCase()} 文件`);

        // 隱藏下拉選單
        if (this.elements.exportDropdown) {
            this.elements.exportDropdown.classList.add('hidden');
        }
    }

    /**
     * 格式化檔案大小
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }
}

// 創建全局實例
export const transcriptionController = new TranscriptionController();

// 預設匯出
export default TranscriptionController;
