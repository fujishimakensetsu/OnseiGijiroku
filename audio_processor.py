"""
音声ファイルの圧縮・分割処理モジュール
PyDubまたはffmpegを使用して100MB以上のファイルを処理
"""
import os
import tempfile
import logging
from typing import List
import shutil
import subprocess
import json

logger = logging.getLogger(__name__)

# Python 3.13のaudioop問題への対応
try:
    from pydub import AudioSegment
    from pydub.utils import mediainfo
    PYDUB_AVAILABLE = True
    logger.info("PyDubを使用した音声処理が利用可能です")
except (ImportError, ModuleNotFoundError) as e:
    PYDUB_AVAILABLE = False
    logger.warning(f"PyDubが利用できません: {str(e)}. ffmpegでの処理を試みます")
    AudioSegment = None
    mediainfo = None

# ffmpegの利用可能性をチェック
def check_ffmpeg_available() -> tuple:
    """
    ffmpegが利用可能かチェック

    Returns:
        (利用可能かどうか, ffmpegコマンドのパス)
    """
    # 一般的なインストール場所
    common_paths = [
        'ffmpeg',  # PATH環境変数から
        'C:/ffmpeg-8.0.1-essentials_build/bin/ffmpeg.exe',
        'C:/ffmpeg/bin/ffmpeg.exe',
        'C:/Program Files/ffmpeg/bin/ffmpeg.exe',
        'C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe',
    ]

    for ffmpeg_path in common_paths:
        try:
            result = subprocess.run(
                [ffmpeg_path, '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return (True, ffmpeg_path)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    return (False, None)

FFMPEG_AVAILABLE, FFMPEG_PATH = check_ffmpeg_available()
if FFMPEG_AVAILABLE:
    logger.info(f"ffmpegを使用した音声処理が利用可能です: {FFMPEG_PATH}")
else:
    logger.warning("ffmpegが利用できません。100MB以上のファイルは処理できません")

class AudioProcessor:
    # 定数定義
    MAX_FILE_SIZE_MB = 100  # 100MB
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    SEGMENT_DURATION_MS = 60 * 60 * 1000  # 1時間（ミリ秒）
    TARGET_BITRATE = "64k"  # 圧縮後のビットレート
    TARGET_SAMPLE_RATE = 16000  # サンプリングレート（16kHz）
    
    def __init__(self):
        """AudioProcessorの初期化"""
        self.temp_files = []
    
    def process_audio(self, file_path: str) -> List[str]:
        """
        音声ファイルを処理（圧縮・分割）

        Args:
            file_path: 入力音声ファイルのパス

        Returns:
            処理済み音声ファイルのパスのリスト
        """
        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"入力ファイルサイズ: {file_size / (1024 * 1024):.2f} MB")

            # PyDubが使えない場合はffmpegを試す
            if not PYDUB_AVAILABLE:
                # 100MB以上のファイルでffmpegが利用可能な場合
                if file_size > self.MAX_FILE_SIZE_BYTES and FFMPEG_AVAILABLE:
                    logger.info("ffmpegを使用してファイルを圧縮・分割します")
                    return self._split_audio_with_ffmpeg(file_path, size_based=True)

                # ffmpegも使えない場合
                if file_size > self.MAX_FILE_SIZE_BYTES:
                    logger.error(
                        f"ファイルサイズが {file_size / (1024 * 1024):.2f} MB で100MBを超えています。"
                        f"PyDubもffmpegも利用できないため、分割処理ができません。"
                    )
                    raise ValueError(
                        f"ファイルサイズが大きすぎます ({file_size / (1024 * 1024):.2f} MB)。\n"
                        f"ffmpegをインストールするか、100MB以下のファイルを使用してください。\n"
                        f"ffmpegのインストール方法: FFMPEG_SETUP.mdを参照"
                    )

                logger.warning("音声処理機能が無効のため、元のファイルをそのまま使用します")
                # 一時コピーを作成
                _, ext = os.path.splitext(file_path)
                output_path = tempfile.mktemp(suffix=ext)
                shutil.copy2(file_path, output_path)
                self.temp_files.append(output_path)
                return [output_path]

            # 音声ファイルの読み込み
            audio = AudioSegment.from_file(file_path)
            duration_hours = len(audio) / (1000 * 60 * 60)
            logger.info(
                f"音声情報 - 長さ: {len(audio) / 1000:.2f}秒 ({duration_hours:.2f}時間), "
                f"チャンネル: {audio.channels}, サンプルレート: {audio.frame_rate}Hz"
            )

            # 常に圧縮を適用（Gemini APIへのアップロード時間を短縮）
            logger.info("音声ファイルを圧縮します（モノラル、16kHz）")
            audio = self._compress_audio(audio)

            # 100MB以上のファイル、または1時間以上の音声は分割を行う
            needs_split = (
                file_size > self.MAX_FILE_SIZE_BYTES or
                len(audio) > self.SEGMENT_DURATION_MS
            )

            # 圧縮後のサイズを確認するため一時出力
            temp_compressed = tempfile.mktemp(suffix=".mp3")
            audio.export(temp_compressed, format="mp3", bitrate=self.TARGET_BITRATE)
            compressed_size = os.path.getsize(temp_compressed)
            logger.info(f"圧縮後サイズ: {compressed_size / (1024 * 1024):.2f} MB")

            # 圧縮後も100MBを超える場合は強制的に分割
            if compressed_size > self.MAX_FILE_SIZE_BYTES:
                logger.warning(f"圧縮後も {compressed_size / (1024 * 1024):.2f} MB で100MBを超えています。ファイルサイズベースで分割します")
                os.unlink(temp_compressed)  # 一時ファイルを削除
                return self._split_audio_by_size(audio)

            os.unlink(temp_compressed)  # 一時ファイルを削除

            # 分割処理（時間ベース）
            if needs_split:
                logger.info(f"音声ファイルを1時間ごとに分割します")
                return self._split_audio(audio)
            else:
                # 分割不要の場合は圧縮済みファイルを返す
                output_path = tempfile.mktemp(suffix=".mp3")
                audio.export(output_path, format="mp3", bitrate=self.TARGET_BITRATE)
                output_size = os.path.getsize(output_path)
                logger.info(f"処理完了 - 出力サイズ: {output_size / (1024 * 1024):.2f} MB")
                self.temp_files.append(output_path)
                return [output_path]

        except Exception as e:
            logger.error(f"音声処理エラー: {str(e)}")
            raise
    
    def _compress_audio(self, audio: AudioSegment) -> AudioSegment:
        """
        音声ファイルを圧縮
        
        Args:
            audio: 圧縮前の音声データ
            
        Returns:
            圧縮後の音声データ
        """
        # モノラル化
        if audio.channels > 1:
            logger.info("ステレオからモノラルに変換")
            audio = audio.set_channels(1)
        
        # サンプリングレート変更
        if audio.frame_rate != self.TARGET_SAMPLE_RATE:
            logger.info(f"サンプリングレートを {audio.frame_rate}Hz から {self.TARGET_SAMPLE_RATE}Hz に変更")
            audio = audio.set_frame_rate(self.TARGET_SAMPLE_RATE)
        
        return audio
    
    def _split_audio(self, audio: AudioSegment) -> List[str]:
        """
        音声ファイルを1時間ごとのセグメントに分割

        Args:
            audio: 分割する音声データ

        Returns:
            分割された音声ファイルのパスのリスト
        """
        total_duration = len(audio)
        segment_paths = []

        # セグメント数を計算
        num_segments = (total_duration // self.SEGMENT_DURATION_MS) + 1
        total_hours = total_duration / (1000 * 60 * 60)
        logger.info(f"音声を {num_segments} 個のセグメント（1時間ごと）に分割 - 合計長さ: {total_hours:.2f}時間")

        for i in range(num_segments):
            start_ms = i * self.SEGMENT_DURATION_MS
            end_ms = min((i + 1) * self.SEGMENT_DURATION_MS, total_duration)

            # セグメントを抽出
            segment = audio[start_ms:end_ms]

            # 一時ファイルに保存
            output_path = tempfile.mktemp(suffix=f"_segment_{i+1}.mp3")
            segment.export(
                output_path,
                format="mp3",
                bitrate=self.TARGET_BITRATE
            )

            segment_size = os.path.getsize(output_path)
            start_hours = start_ms / (1000 * 60 * 60)
            end_hours = end_ms / (1000 * 60 * 60)
            logger.info(
                f"セグメント {i+1}/{num_segments} 作成 "
                f"({start_hours:.2f}時間 - {end_hours:.2f}時間, {segment_size / (1024 * 1024):.2f} MB)"
            )

            segment_paths.append(output_path)
            self.temp_files.append(output_path)

        return segment_paths

    def _split_audio_by_size(self, audio: AudioSegment) -> List[str]:
        """
        音声ファイルをサイズベースで分割（圧縮しても100MB以下にならない場合）

        Args:
            audio: 分割する音声データ

        Returns:
            分割された音声ファイルのパスのリスト
        """
        total_duration = len(audio)
        segment_paths = []

        # 推定: 1ミリ秒あたり約80バイト（64kbps, 16kHz, mono）
        # 安全マージンを考慮して90MBをターゲットに
        TARGET_SIZE_BYTES = 90 * 1024 * 1024
        estimated_bytes_per_ms = 80
        segment_duration_ms = int(TARGET_SIZE_BYTES / estimated_bytes_per_ms)

        # セグメント数を計算
        num_segments = (total_duration // segment_duration_ms) + 1
        total_hours = total_duration / (1000 * 60 * 60)
        segment_hours = segment_duration_ms / (1000 * 60 * 60)

        logger.info(
            f"音声を {num_segments} 個のセグメント（約{segment_hours:.2f}時間ごと、90MB目標）に分割 - "
            f"合計長さ: {total_hours:.2f}時間"
        )

        for i in range(num_segments):
            start_ms = i * segment_duration_ms
            end_ms = min((i + 1) * segment_duration_ms, total_duration)

            # セグメントを抽出
            segment = audio[start_ms:end_ms]

            # 一時ファイルに保存
            output_path = tempfile.mktemp(suffix=f"_segment_{i+1}.mp3")
            segment.export(
                output_path,
                format="mp3",
                bitrate=self.TARGET_BITRATE
            )

            segment_size = os.path.getsize(output_path)
            start_hours = start_ms / (1000 * 60 * 60)
            end_hours = end_ms / (1000 * 60 * 60)

            # もし分割後も100MBを超える場合は警告
            if segment_size > self.MAX_FILE_SIZE_BYTES:
                logger.warning(
                    f"警告: セグメント {i+1} が {segment_size / (1024 * 1024):.2f} MB で100MBを超えています"
                )

            logger.info(
                f"セグメント {i+1}/{num_segments} 作成 "
                f"({start_hours:.2f}時間 - {end_hours:.2f}時間, {segment_size / (1024 * 1024):.2f} MB)"
            )

            segment_paths.append(output_path)
            self.temp_files.append(output_path)

        return segment_paths

    def _split_audio_with_ffmpeg(self, file_path: str, size_based: bool = False) -> List[str]:
        """
        ffmpegを使用して音声ファイルを1時間ごとに分割

        Args:
            file_path: 入力音声ファイルのパス

        Returns:
            分割された音声ファイルのパスのリスト
        """
        segment_paths = []

        # ffprobeのパスを取得
        if FFMPEG_PATH == 'ffmpeg':
            ffprobe_path = 'ffprobe'
        else:
            ffprobe_path = FFMPEG_PATH.replace('ffmpeg.exe', 'ffprobe.exe')

        try:
            # 音声ファイルの長さを取得
            probe_cmd = [
                ffprobe_path,
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                file_path
            ]

            probe_result = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if probe_result.returncode != 0:
                raise RuntimeError(f"ffprobeエラー: {probe_result.stderr}")

            duration_data = json.loads(probe_result.stdout)
            total_duration = float(duration_data['format']['duration'])
            total_hours = total_duration / 3600

            logger.info(f"音声の長さ: {total_duration:.2f}秒 ({total_hours:.2f}時間)")

            # サイズベースまたは時間ベースで分割
            if size_based:
                # 推定: 64kbps = 8KB/秒、90MBをターゲット
                TARGET_SIZE_BYTES = 90 * 1024 * 1024
                estimated_bytes_per_sec = 8 * 1024
                segment_duration = int(TARGET_SIZE_BYTES / estimated_bytes_per_sec)
                logger.info(f"サイズベース分割: 各セグメント約{segment_duration/3600:.2f}時間（90MB目標）")
            else:
                # 1時間 = 3600秒
                segment_duration = 3600
                logger.info("時間ベース分割: 各セグメント1時間")

            num_segments = int(total_duration // segment_duration) + 1

            logger.info(f"音声を {num_segments} 個のセグメントに分割")

            for i in range(num_segments):
                start_time = i * segment_duration

                # 最後のセグメントの長さを調整
                if i == num_segments - 1:
                    duration = total_duration - start_time
                else:
                    duration = segment_duration

                # 出力ファイルパス
                output_path = tempfile.mktemp(suffix=f"_segment_{i+1}.mp3")

                # ffmpegコマンドで分割
                split_cmd = [
                    FFMPEG_PATH,
                    '-i', file_path,
                    '-ss', str(start_time),
                    '-t', str(duration),
                    '-c:a', 'libmp3lame',
                    '-b:a', '64k',
                    '-ar', '16000',
                    '-ac', '1',
                    '-y',
                    output_path
                ]

                logger.info(f"セグメント {i+1}/{num_segments} を処理中 ({start_time/3600:.2f}h - {(start_time+duration)/3600:.2f}h)")

                split_result = subprocess.run(
                    split_cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if split_result.returncode != 0:
                    logger.error(f"ffmpegエラー: {split_result.stderr}")
                    raise RuntimeError(f"セグメント {i+1} の処理に失敗しました")

                segment_size = os.path.getsize(output_path)
                logger.info(
                    f"セグメント {i+1}/{num_segments} 作成完了 "
                    f"({start_time/3600:.2f}時間 - {(start_time+duration)/3600:.2f}時間, "
                    f"{segment_size / (1024 * 1024):.2f} MB)"
                )

                segment_paths.append(output_path)
                self.temp_files.append(output_path)

            return segment_paths

        except subprocess.TimeoutExpired:
            logger.error("ffmpegの処理がタイムアウトしました")
            raise RuntimeError("音声ファイルの処理がタイムアウトしました")
        except Exception as e:
            logger.error(f"ffmpeg処理エラー: {str(e)}")
            # エラー時は作成したファイルをクリーンアップ
            for path in segment_paths:
                if os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception:
                        pass
            raise

    def cleanup(self):
        """一時ファイルのクリーンアップ"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"一時ファイル削除: {temp_file}")
            except Exception as e:
                logger.warning(f"一時ファイル削除エラー: {temp_file} - {str(e)}")
        
        self.temp_files.clear()
    
    def __del__(self):
        """デストラクタ - 一時ファイルのクリーンアップ"""
        self.cleanup()
