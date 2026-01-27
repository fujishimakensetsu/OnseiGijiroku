"""
音声ファイルの圧縮処理モジュール
PyDubまたはffmpegを使用してファイルを圧縮
"""
import os
import tempfile
import logging
from typing import List
import shutil
import subprocess

logger = logging.getLogger(__name__)

# Python 3.13のaudioop問題への対応
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
    logger.info("PyDubを使用した音声処理が利用可能です")
except (ImportError, ModuleNotFoundError) as e:
    PYDUB_AVAILABLE = False
    logger.warning(f"PyDubが利用できません: {str(e)}. ffmpegでの処理を試みます")
    AudioSegment = None

# ffmpegの利用可能性をチェック
def check_ffmpeg_available() -> tuple:
    """
    ffmpegが利用可能かチェック

    Returns:
        (利用可能かどうか, ffmpegコマンドのパス)
    """
    common_paths = [
        'ffmpeg',
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
    logger.warning("ffmpegが利用できません")

class AudioProcessor:
    TARGET_BITRATE = "64k"
    TARGET_SAMPLE_RATE = 16000

    def __init__(self):
        """AudioProcessorの初期化"""
        self.temp_files = []

    def process_audio(self, file_path: str) -> List[str]:
        """
        音声ファイルを処理（圧縮のみ、分割なし）

        Args:
            file_path: 入力音声ファイルのパス

        Returns:
            処理済み音声ファイルのパスのリスト（1ファイルのみ）
        """
        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"入力ファイルサイズ: {file_size / (1024 * 1024):.2f} MB")

            # PyDubが使えない場合
            if not PYDUB_AVAILABLE:
                if FFMPEG_AVAILABLE:
                    logger.info("ffmpegを使用してファイルを圧縮します")
                    return [self._compress_with_ffmpeg(file_path)]
                else:
                    logger.warning("音声処理機能が無効のため、元のファイルをそのまま使用します")
                    _, ext = os.path.splitext(file_path)
                    output_path = tempfile.mktemp(suffix=ext)
                    shutil.copy2(file_path, output_path)
                    self.temp_files.append(output_path)
                    return [output_path]

            # PyDubで音声ファイルを読み込み
            audio = AudioSegment.from_file(file_path)
            duration_minutes = len(audio) / (1000 * 60)
            logger.info(
                f"音声情報 - 長さ: {duration_minutes:.2f}分, "
                f"チャンネル: {audio.channels}, サンプルレート: {audio.frame_rate}Hz"
            )

            # 圧縮処理
            logger.info("音声ファイルを圧縮します（モノラル、16kHz）")
            audio = self._compress_audio(audio)

            # 圧縮済みファイルを出力
            output_path = tempfile.mktemp(suffix=".mp3")
            audio.export(output_path, format="mp3", bitrate=self.TARGET_BITRATE)
            output_size = os.path.getsize(output_path)
            logger.info(f"圧縮完了 - 出力サイズ: {output_size / (1024 * 1024):.2f} MB")
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

    def _compress_with_ffmpeg(self, file_path: str) -> str:
        """
        ffmpegを使用して音声ファイルを圧縮

        Args:
            file_path: 入力音声ファイルのパス

        Returns:
            圧縮された音声ファイルのパス
        """
        output_path = tempfile.mktemp(suffix=".mp3")

        cmd = [
            FFMPEG_PATH,
            '-i', file_path,
            '-c:a', 'libmp3lame',
            '-b:a', '64k',
            '-ar', '16000',
            '-ac', '1',
            '-y',
            output_path
        ]

        logger.info("ffmpegで音声ファイルを圧縮中...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10分タイムアウト
        )

        if result.returncode != 0:
            logger.error(f"ffmpegエラー: {result.stderr}")
            raise RuntimeError(f"音声圧縮に失敗しました")

        output_size = os.path.getsize(output_path)
        logger.info(f"圧縮完了 - 出力サイズ: {output_size / (1024 * 1024):.2f} MB")

        self.temp_files.append(output_path)
        return output_path

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
