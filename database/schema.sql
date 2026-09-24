-- Midair.io データベーススキーマ (MySQL 8.x / utf8mb4)
-- SQLite で動かす場合は不要（起動時に自動作成される）。

CREATE DATABASE IF NOT EXISTS midair
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE midair;

-- 1. ユーザー（リスナー/パーソナリティ/管理者）
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NULL,       -- Discord OAuth等の場合はNULL許容
    discord_id VARCHAR(64) NULL UNIQUE,     -- Discord連携用ID
    avatar_url VARCHAR(500) NULL,
    bio VARCHAR(255) NULL,
    role ENUM('listener', 'broadcaster', 'admin') DEFAULT 'listener',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 放送局・周波数（開局データ）
CREATE TABLE IF NOT EXISTS stations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,                  -- 開局したユーザー
    frequency DECIMAL(4,1) NOT NULL UNIQUE, -- 例: 88.5 (MHz), 76.0〜94.9
    callsign VARCHAR(50) NOT NULL,          -- コールサイン/局名
    description TEXT NULL,
    theme_color VARCHAR(10) DEFAULT '#ffffff',
    current_youtube_id VARCHAR(32) NULL,    -- 現在再生中のBGM
    playback_started_at DATETIME NULL,      -- BGM同期用の開始時刻
    is_live TINYINT(1) DEFAULT 0,           -- 1: 放送中, 0: 休止中（statusから同期）
    status ENUM('reserved','live','off_air') DEFAULT 'live',  -- ライフサイクル状態
    scheduled_start DATETIME NULL,          -- 予約開始時刻（RESERVED→LIVE）
    scheduled_end DATETIME NULL,            -- 予約終了時刻（LIVE→OFF AIR）
    ai_dj_enabled TINYINT(1) DEFAULT 1,     -- AI DJを稼働させるか
    ai_dj_prompt TEXT NULL,                 -- AI DJのキャラクター指示文
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_frequency (frequency)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 番組枠（番組表/タイムテーブル）
CREATE TABLE IF NOT EXISTS programs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    station_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,            -- 番組名
    description TEXT NULL,
    start_time DATETIME NOT NULL,           -- 開始日時
    end_time DATETIME NOT NULL,             -- 終了日時
    default_youtube_id VARCHAR(32) NULL,    -- 番組開始時に自動セットされるBGM
    is_archived TINYINT(1) DEFAULT 0,       -- 放送終了後にアーカイブ化するか
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE CASCADE,
    INDEX idx_schedule (start_time, end_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. メッセージログ
CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    station_id INT NOT NULL,
    session_id INT NULL,                    -- 放送セッションID（自動記録）
    user_id INT NULL,                       -- ログインユーザーID（未ログイン時はNULL）
    sender_name VARCHAR(50) NOT NULL DEFAULT '名無しのリスナー',
    content TEXT NOT NULL,
    offset_seconds INT NOT NULL DEFAULT 0,  -- セッション開始からの経過秒（タイムシフト再生用）
    youtube_id VARCHAR(32) NULL,            -- リクエスト曲
    is_dj TINYINT(1) DEFAULT 0,             -- 1: AI DJの発言
    is_broadcaster TINYINT(1) DEFAULT 0,    -- 1: パーソナリティ（開局者）の発言
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_station_created (station_id, created_at),
    INDEX idx_session_offset (session_id, offset_seconds)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. お気に入り周波数（リスナーのプリセット保存）
CREATE TABLE IF NOT EXISTS station_favorites (
    user_id INT NOT NULL,
    station_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, station_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. 周波数の時間枠予約（放送前の枠取り / 開局準備中）
CREATE TABLE IF NOT EXISTS reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    frequency DECIMAL(4,1) NOT NULL,        -- 予約する周波数 76.0〜94.9
    callsign VARCHAR(50) NOT NULL DEFAULT '',
    note TEXT NULL,
    start_time DATETIME NOT NULL,           -- 予約開始
    end_time DATETIME NOT NULL,             -- 予約終了
    status ENUM('active','cancelled','expired') DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_res_freq_time (frequency, start_time, end_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. 放送セッション（予約の有無を問わず、ON AIR〜OFF AIR の1区切りを自動記録）
CREATE TABLE IF NOT EXISTS broadcast_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    station_id INT NOT NULL,
    session_title VARCHAR(150) NOT NULL DEFAULT '突発ゲリラ放送',
    program_reservation_id INT NULL,          -- 番組予約があった場合はそのID
    started_at DATETIME NOT NULL,             -- ON AIRになった瞬間
    ended_at DATETIME NULL,                   -- OFF AIRになった瞬間（NULLは放送中）
    total_messages INT UNSIGNED DEFAULT 0,    -- 累計発言数（クローズ時に自動集計）
    peak_listeners INT UNSIGNED DEFAULT 0,    -- 最大同時接続リスナー数
    is_public TINYINT(1) NOT NULL DEFAULT 1,  -- 誰でも見れるパブリック公開フラグ
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE CASCADE,
    INDEX idx_station_sessions (station_id, started_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. 放送楽曲履歴（セッション中に流れたYouTube曲のタイムスタンプ記録）
CREATE TABLE IF NOT EXISTS session_tracks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    youtube_id VARCHAR(32) NOT NULL,
    title VARCHAR(255) NULL,
    started_offset_sec INT NOT NULL DEFAULT 0, -- セッション開始から何秒後に再生開始されたか
    played_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES broadcast_sessions(id) ON DELETE CASCADE,
    INDEX idx_session_track (session_id, started_offset_sec)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
