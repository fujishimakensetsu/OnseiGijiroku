# Google Cloud Storage セットアップガイド

このガイドでは、音声議事録AIアプリケーションでGoogle Cloud Storage（GCS）を使用するための設定手順を説明します。

## 前提条件

- Google Cloud Projectが作成済み
- gcloud CLIがインストール済み
- GitHub ActionsでWorkload Identity設定済み

## 1. GCSバケットの作成

### 1-1. プロジェクトIDを確認
```bash
gcloud config get-value project
```

### 1-2. バケットを作成
```bash
# プロジェクトIDを環境変数に設定
export PROJECT_ID=$(gcloud config get-value project)

# バケット名を設定（グローバルで一意である必要があります）
export BUCKET_NAME="${PROJECT_ID}-audio-uploads"

# バケットを作成（asia-northeast1リージョン）
gcloud storage buckets create gs://${BUCKET_NAME} \
  --location=asia-northeast1 \
  --uniform-bucket-level-access

# ライフサイクルルールを設定（アップロード後24時間で自動削除）
cat > lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 1
        }
      }
    ]
  }
}
EOF

gcloud storage buckets update gs://${BUCKET_NAME} --lifecycle-file=lifecycle.json
rm lifecycle.json
```

### 1-3. CORSを設定（フロントエンドからの直接アップロード用）
```bash
cat > cors.json <<EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "POST", "PUT"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF

gcloud storage buckets update gs://${BUCKET_NAME} --cors-file=cors.json
rm cors.json
```

## 2. サービスアカウントの権限設定

### 2-1. Workload Identityサービスアカウントを確認
```bash
# GitHub Secretsに設定されているサービスアカウントを確認
# 例: minutes-generator@${PROJECT_ID}.iam.gserviceaccount.com
export SERVICE_ACCOUNT="minutes-generator@${PROJECT_ID}.iam.gserviceaccount.com"
```

### 2-2. Storage Admin権限を付与
```bash
# Cloud Runサービスアカウントに Storage Admin ロールを付与
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/storage.admin"
```

### 2-3. 署名付きURL作成用の権限を付与
```bash
# Service Account Token Creator ロールを付与（署名付きURL生成に必要）
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/iam.serviceAccountTokenCreator"
```

## 3. ローカル開発環境の設定

### 3-1. サービスアカウントキーを作成（ローカル開発用）
```bash
# 開発用サービスアカウントキーを作成
gcloud iam service-accounts keys create ./service-account-key.json \
  --iam-account=${SERVICE_ACCOUNT}

# キーファイルのパスを確認
echo "GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/service-account-key.json"
```

### 3-2. .envファイルに設定を追加
```bash
# .envファイルを編集
cat >> .env <<EOF

# Google Cloud Storage設定
GCS_BUCKET_NAME=${BUCKET_NAME}
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
GCP_PROJECT_ID=${PROJECT_ID}
EOF
```

**重要**: `service-account-key.json`は機密情報です。`.gitignore`に追加されていることを確認してください。

## 4. GitHub Secretsの更新

GitHub ActionsでGCSバケット名を使用できるよう、以下のSecretを追加します。

1. GitHubリポジトリの **Settings** > **Secrets and variables** > **Actions** へ移動
2. **New repository secret** をクリック
3. 以下のSecretを追加：
   - Name: `GCS_BUCKET_NAME`
   - Value: `${PROJECT_ID}-audio-uploads`（実際のバケット名）

## 5. 動作確認

### 5-1. バケットが作成されたことを確認
```bash
gcloud storage buckets describe gs://${BUCKET_NAME}
```

### 5-2. サービスアカウント権限を確認
```bash
gcloud projects get-iam-policy ${PROJECT_ID} \
  --flatten="bindings[].members" \
  --filter="bindings.members:${SERVICE_ACCOUNT}"
```

期待される出力：
- `roles/storage.admin`
- `roles/iam.serviceAccountTokenCreator`
- その他既存の権限

## トラブルシューティング

### エラー: "Bucket name already exists"
バケット名はグローバルで一意である必要があります。別の名前を試してください。
```bash
export BUCKET_NAME="${PROJECT_ID}-minutes-audio-$(date +%s)"
```

### エラー: "Permission denied"
サービスアカウントに必要な権限が付与されていることを確認してください。
```bash
gcloud projects get-iam-policy ${PROJECT_ID} \
  --flatten="bindings[].members" \
  --filter="bindings.members:${SERVICE_ACCOUNT}"
```

### ローカル開発で認証エラーが出る場合
```bash
# 環境変数が正しく設定されているか確認
echo $GOOGLE_APPLICATION_CREDENTIALS

# gcloud認証を確認
gcloud auth application-default login
```

## セキュリティのベストプラクティス

1. **本番環境のCORS設定を制限**
   - 開発後は、`origin: ["*"]` を実際のドメインに変更してください
   - 例: `origin: ["https://your-domain.com"]`

2. **ライフサイクルポリシー**
   - アップロードされたファイルは24時間後に自動削除されます
   - 必要に応じて期間を調整してください

3. **サービスアカウントキーの管理**
   - キーファイルは絶対にGitにコミットしないでください
   - 定期的にキーをローテーションしてください

4. **最小権限の原則**
   - 本番環境では、必要最小限の権限のみを付与してください
   - `storage.admin`より細かい権限（`storage.objectCreator`, `storage.objectViewer`）も検討してください

## 次のステップ

GCS設定が完了したら、以下のファイルが更新されます：
- `requirements.txt`: GCSライブラリ追加
- `main.py`: 署名付きURL生成とGCS読み取り処理
- `app.js`: GCS直接アップロード実装
- `.env.example`: GCS設定例の追加
- `.github/workflows/deploy.yml`: GCS_BUCKET_NAME環境変数の追加

これらの変更により、大容量ファイル（500MB以上）も分割なしで処理できるようになります。
