"""
認証サービス - パスワードのみの認証（GitHub Secrets対応）
"""
from datetime import datetime, timedelta
from typing import Optional, Dict
import jwt
import bcrypt
import os
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        """認証サービスの初期化"""
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 480  # 8時間

        # アクセスパスワード（環境変数から取得）
        # GitHub Secretsで APP_ACCESS_PASSWORD を設定
        self.access_password = os.getenv("APP_ACCESS_PASSWORD")

        if self.access_password:
            logger.info("アクセスパスワードが環境変数から設定されました")
        else:
            logger.warning("APP_ACCESS_PASSWORDが設定されていません。デフォルトパスワードを使用します")
            self.access_password = "demo123"  # デフォルト（開発用）

    async def authenticate_password(self, password: str) -> Optional[Dict]:
        """
        パスワード認証

        Args:
            password: アクセスパスワード

        Returns:
            認証成功時はユーザー情報、失敗時はNone
        """
        try:
            # デバッグ: 環境変数の状態をログ出力
            logger.info(f"環境変数APP_ACCESS_PASSWORD設定状況: {'設定済み' if os.getenv('APP_ACCESS_PASSWORD') else '未設定'}")
            logger.info(f"使用中のパスワード長: {len(self.access_password) if self.access_password else 0}")

            # パスワードの検証
            if password == self.access_password:
                logger.info("パスワード認証成功")
                return {
                    "username": "user",
                    "name": "ユーザー"
                }
            else:
                logger.warning(f"パスワードが一致しません（入力長: {len(password)}, 期待長: {len(self.access_password) if self.access_password else 0}）")
                return None

        except Exception as e:
            logger.error(f"認証処理エラー: {str(e)}")
            return None

    def create_access_token(self, data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        JWTアクセストークンを生成

        Args:
            data: トークンに含めるデータ
            expires_delta: 有効期限（デフォルト: 8時間）

        Returns:
            JWTトークン
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        to_encode.update({"exp": expire})

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        logger.info(f"アクセストークン生成: {data.get('sub')}, 有効期限: {expire}")
        return encoded_jwt
