/**
 * 轉錄服務
 * 管理語音轉文字的業務邏輯
 */

import { apiService } from './ApiService.js';
import { isValidYouTubeUrl, isValidFileType, isValidFileSize } from '../utils/validators.js';

export class TranscriptionService {
    constructor() {
        this.currentTask = null;
        this.isProcessing = false;
    }

    /**
     * 提交轉錄任務
     * @param {Object} options - 轉錄選項
     * @returns {Promise} - 轉錄結果
     */
    async submit(options) {
        const {
            file,
            youtubeUrl,
            language,
            withDiarization,
            vadEnabled,
            vadSettings,
            downloadVideo,
            downloadThumbnail,
            clientId
        } = options;

        // 驗證輸入
        const validation = this.validateInput(file, youtubeUrl);
        if (!validation.valid) {
            throw new Error(validation.error);
        }

        // 創建 FormData
        const formData = this.createFormData({
            file,
            youtubeUrl,
            language,
            withDiarization,
            vadEnabled,
            vadSettings,
            downloadVideo,
            downloadThumbnail,
            clientId
        });

        try {
            this.isProcessing = true;

            const result = await apiService.transcription.submit(formData);

            this.currentTask = result;

            return result;
        } catch (error) {
            console.error('提交轉錄任務失敗:', error);
            throw error;
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * 驗證輸入
     * @param {File} file - 檔案對象
     * @param {string} youtubeUrl - YouTube URL
     * @returns {Object} - 驗證結果
     */
    validateInput(file, youtubeUrl) {
        // 檢查是否有文件或 YouTube URL
        if (!file && !youtubeUrl) {
            return {
                valid: false,
                error: '請上傳音頻文件或輸入 YouTube 連結'
            };
        }

        // 驗證文件
        if (file) {
            if (!isValidFileType(file)) {
                return {
                    valid: false,
                    error: '不支持的文件類型。支持的格式: MP3, WAV, M4A, FLAC, OGG'
                };
            }

            if (!isValidFileSize(file)) {
                return {
                    valid: false,
                    error: '文件大小超過限制（最大 500MB）'
                };
            }
        }

        // 驗證 YouTube URL
        if (youtubeUrl && !isValidYouTubeUrl(youtubeUrl)) {
            return {
                valid: false,
                error: '無效的 YouTube 連結'
            };
        }

        return { valid: true };
    }

    /**
     * 創建表單數據
     * @param {Object} options - 選項
     * @returns {FormData} - 表單數據
     */
    createFormData(options) {
        const {
            file,
            youtubeUrl,
            language,
            withDiarization,
            vadEnabled,
            vadSettings,
            downloadVideo,
            downloadThumbnail,
            clientId
        } = options;

        const formData = new FormData();

        // 添加文件或 YouTube URL
        if (file) {
            formData.append('file', file);
        }

        if (youtubeUrl) {
            formData.append('youtube_url', youtubeUrl);
        }

        // 添加基本選項
        formData.append('model', 'whisper-1');
        formData.append('response_format', 'verbose_json');

        if (clientId) {
            formData.append('client_id', clientId);
        }

        // 添加語言
        if (language) {
            formData.append('language', language);
        }

        // 添加說話者分離
        formData.append('with_diarization', withDiarization || false);

        // 添加 VAD 設定
        formData.append('vad_filter', vadEnabled || false);

        if (vadEnabled && vadSettings) {
            if (vadSettings.minSilenceDuration) {
                formData.append('min_silence_duration_ms', vadSettings.minSilenceDuration);
            }
            if (vadSettings.speechPad) {
                formData.append('speech_pad_ms', vadSettings.speechPad);
            }
        }

        // 添加 YouTube 下載選項
        if (youtubeUrl) {
            formData.append('download_video', downloadVideo !== undefined ? downloadVideo : false);
            formData.append('download_thumbnail', downloadThumbnail !== undefined ? downloadThumbnail : true);
        }

        return formData;
    }

    /**
     * 取消當前任務
     */
    cancel() {
        this.isProcessing = false;
        this.currentTask = null;
    }

    /**
     * 獲取當前任務
     * @returns {Object} - 當前任務
     */
    getCurrentTask() {
        return this.currentTask;
    }

    /**
     * 檢查是否正在處理
     * @returns {boolean} - 是否正在處理
     */
    isProcessingTask() {
        return this.isProcessing;
    }

    /**
     * 格式化進度數據
     * @param {Object} data - WebSocket 進度數據
     * @returns {Object} - 格式化後的進度數據
     */
    formatProgressData(data) {
        const { type, progress, stage } = data;

        return {
            type,
            progress: progress || 0,
            stage: stage || 'initializing',
            message: this.getStageMessage(stage),
            timestamp: Date.now()
        };
    }

    /**
     * 獲取階段訊息
     * @param {string} stage - 階段名稱
     * @returns {string} - 階段訊息
     */
    getStageMessage(stage) {
        const stageMessages = {
            'initializing': '初始化中...',
            'file_processing': '處理檔案中...',
            'downloading': '下載中...',
            'transcribing': '語音轉錄中...',
            'diarizing': '說話者識別中...',
            'post_processing': '後處理中...',
            'saving_files': '保存檔案中...',
            'completed': '完成',
            'error': '發生錯誤'
        };

        return stageMessages[stage] || '處理中...';
    }

    /**
     * 處理分段數據
     * @param {Object} segment - 分段數據
     * @returns {Object} - 格式化後的分段
     */
    formatSegment(segment) {
        return {
            id: segment.id,
            start: segment.start,
            end: segment.end,
            text: segment.text,
            speaker: segment.speaker || null,
            timeRange: this.formatTimeRange(segment.start, segment.end)
        };
    }

    /**
     * 格式化時間範圍
     * @param {number} start - 開始時間（秒）
     * @param {number} end - 結束時間（秒）
     * @returns {string} - 時間範圍字符串
     */
    formatTimeRange(start, end) {
        const formatTime = (seconds) => {
            const date = new Date(seconds * 1000);
            const mm = date.getUTCMinutes().toString().padStart(2, '0');
            const ss = date.getUTCSeconds().toString().padStart(2, '0');
            const ms = Math.floor(date.getUTCMilliseconds() / 10).toString().padStart(2, '0');
            return `${mm}:${ss}.${ms}`;
        };

        return `${formatTime(start)} - ${formatTime(end)}`;
    }

    /**
     * 獲取說話者顏色類
     * @param {string} speaker - 說話者標識
     * @returns {string} - CSS 類名
     */
    getSpeakerColorClass(speaker) {
        const speakerColors = {
            "SPEAKER_00": "bg-blue-100 text-blue-800",
            "SPEAKER_01": "bg-green-100 text-green-800",
            "SPEAKER_02": "bg-purple-100 text-purple-800",
            "SPEAKER_03": "bg-yellow-100 text-yellow-800",
            "SPEAKER_04": "bg-red-100 text-red-800",
            "未知": "bg-gray-100 text-gray-800"
        };

        return speakerColors[speaker] || "bg-gray-100 text-gray-800";
    }

    /**
     * 導出轉錄文本
     * @param {Array} segments - 分段數組
     * @param {string} format - 導出格式 ('txt' 或 'srt')
     * @returns {string} - 導出內容
     */
    exportTranscript(segments, format = 'txt') {
        if (format === 'srt') {
            return this.exportToSRT(segments);
        } else {
            return this.exportToTXT(segments);
        }
    }

    /**
     * 導出為 TXT
     * @param {Array} segments - 分段數組
     * @returns {string} - TXT 內容
     */
    exportToTXT(segments) {
        return segments.map(seg => seg.text).join('\n\n');
    }

    /**
     * 導出為 SRT
     * @param {Array} segments - 分段數組
     * @returns {string} - SRT 內容
     */
    exportToSRT(segments) {
        return segments.map((seg, index) => {
            const startTime = this.formatSRTTime(seg.start);
            const endTime = this.formatSRTTime(seg.end);

            return `${index + 1}\n${startTime} --> ${endTime}\n${seg.text}\n`;
        }).join('\n');
    }

    /**
     * 格式化 SRT 時間
     * @param {number} seconds - 秒數
     * @returns {string} - SRT 時間格式
     */
    formatSRTTime(seconds) {
        const date = new Date(seconds * 1000);
        const hh = Math.floor(seconds / 3600).toString().padStart(2, '0');
        const mm = date.getUTCMinutes().toString().padStart(2, '0');
        const ss = date.getUTCSeconds().toString().padStart(2, '0');
        const ms = date.getUTCMilliseconds().toString().padStart(3, '0');

        return `${hh}:${mm}:${ss},${ms}`;
    }
}

// 創建全局轉錄服務實例
export const transcriptionService = new TranscriptionService();

// 預設匯出
export default TranscriptionService;
