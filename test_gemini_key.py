"""
Gemini APIキーをテストするスクリプト
"""
import os
import google.generativeai as genai
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

def test_gemini_api():
    """Gemini APIキーをテスト"""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("❌ GEMINI_API_KEYが設定されていません")
        print("   .envファイルにGEMINI_API_KEY=your-key-hereを追加してください")
        return False

    print(f"✅ APIキーが見つかりました: {api_key[:20]}...")

    try:
        # Gemini APIを設定
        genai.configure(api_key=api_key)

        # テストメッセージを送信
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content("こんにちは")

        print("✅ Gemini APIが正常に動作しています")
        print(f"   レスポンス: {response.text[:100]}")
        return True

    except Exception as e:
        print(f"❌ Gemini APIエラー: {str(e)}")
        print("   APIキーが無効か、APIが有効化されていない可能性があります")
        print("   https://aistudio.google.com/app/apikey でキーを確認してください")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Gemini APIキー テスト")
    print("=" * 60)
    test_gemini_api()
    print("=" * 60)
